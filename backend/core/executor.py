from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from core.event_bus import event_bus
from core.module_registry import ModuleManifest
from core.scanner_base import ScanError, ScannerBase
from storage.db import Scan, ScanDiffLog, ScanItem, WhitelistEntry, db

logger = logging.getLogger(__name__)


async def dispatch_scan(manifest: ModuleManifest) -> str:
    """API wrapper: tạo record running, chạy scan nền, trả scan_id ngay."""
    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id=manifest.id, status="running", started_at=datetime.utcnow()))
        s.commit()
    asyncio.create_task(execute_scan(manifest, scan_id))
    return scan_id


async def execute_scan(manifest: ModuleManifest, scan_id: str) -> None:
    """Vòng đời 1 lượt quét: chạy module → whitelist → diffing → lưu → broadcast.

    Đây là nơi duy nhất bọc exception của mọi module (mục 8 BACKEND.md).
    """
    module_id = manifest.id
    scanner = manifest.scanner_cls()
    logger.info("Scan bắt đầu: module=%s scan_id=%s", module_id, scan_id)

    # Đảm bảo record scan tồn tại (dispatch_scan tạo trước khi chạy nền;
    # test/scheduler có thể gọi trực tiếp execute_scan mà không có record).
    with db.session() as s:
        if s.get(Scan, scan_id) is None:
            s.add(Scan(id=scan_id, module_id=module_id, status="running", started_at=datetime.utcnow()))
            s.commit()

    async def progress_cb(current: int, total: int, message: str) -> None:
        await event_bus.publish(
            f"scan.{scan_id}.progress",
            {"type": "progress", "current": current, "total": total, "message": message},
        )

    try:
        result = await scanner.run(progress_cb=progress_cb)

        with db.session() as s:
            prev = _previous_scan(s, module_id, scan_id)
            prev_keys = _keys_of_scan(s, prev.id) if prev else set()
            whitelisted = _whitelist_keys(s, module_id)
            current_keys = set()

            for item in result.items:
                key = scanner.get_whitelist_key(item)
                severity = "safe" if key in whitelisted else item.severity
                is_new = key not in prev_keys
                current_keys.add(key)
                s.add(
                    ScanItem(
                        scan_id=scan_id,
                        module_id=module_id,
                        whitelist_key=key,
                        severity=severity,
                        title=item.title,
                        detail_json=json.dumps(item.detail, ensure_ascii=False),
                        is_new=is_new,
                    )
                )
                await event_bus.publish(
                    f"scan.{scan_id}.item",
                    {
                        "type": "item_found",
                        "item": {
                            "severity": severity,
                            "title": item.title,
                            "detail": item.detail,
                            "is_new": is_new,
                        },
                    },
                )

            for gone_key in sorted(prev_keys - current_keys):
                s.add(
                    ScanDiffLog(
                        module_id=module_id,
                        whitelist_key=gone_key,
                        change_type="disappeared",
                        scan_id=scan_id,
                        created_at=datetime.utcnow(),
                    )
                )
            for new_key in sorted(current_keys - prev_keys):
                s.add(
                    ScanDiffLog(
                        module_id=module_id,
                        whitelist_key=new_key,
                        change_type="appeared",
                        scan_id=scan_id,
                        created_at=datetime.utcnow(),
                    )
                )

            row = s.get(Scan, scan_id)
            row.status = "done"
            row.finished_at = datetime.utcnow()
            row.summary_json = json.dumps(result.summary, ensure_ascii=False)
            row.partial_result = result.partial_result
            s.commit()

        await event_bus.publish(
            f"scan.{scan_id}.done",
            {
                "type": "done",
                "scan_id": scan_id,
                "summary": result.summary,
                "partial_result": result.partial_result,
                "module_id": module_id,
            },
        )
        logger.info("Scan hoàn tất: module=%s scan_id=%s", module_id, scan_id)

    except ScanError as exc:
        logger.error("Scan bị chặn (code=%s): %s", exc.code, exc.message)
        _mark_failed(scan_id, exc.code, exc.message)
        await event_bus.publish(
            f"scan.{scan_id}.error",
            {"type": "error", "code": exc.code, "message": exc.message},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scan thất bại module=%s scan_id=%s", module_id, scan_id)
        _mark_failed(scan_id, "SCAN_FAILED", str(exc))
        await event_bus.publish(
            f"scan.{scan_id}.error",
            {"type": "error", "code": "SCAN_FAILED", "message": f"Quét thất bại: {exc}"},
        )

    return scan_id


def _mark_failed(scan_id: str, code: str, message: str) -> None:
    with db.session() as s:
        row = s.get(Scan, scan_id)
        if row:
            row.status = "error"
            row.finished_at = datetime.utcnow()
            row.error_message = message
            s.commit()


def _previous_scan(session, module_id: str, exclude_scan_id: str) -> Optional[Scan]:
    return session.execute(
        select(Scan)
        .where(Scan.module_id == module_id, Scan.id != exclude_scan_id, Scan.status == "done", Scan.partial_result.is_(False))
        .order_by(Scan.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _keys_of_scan(session, scan_id: str) -> set[str]:
    rows = session.execute(select(ScanItem.whitelist_key).where(ScanItem.scan_id == scan_id)).all()
    return {kw[0] for kw in rows}


def _whitelist_keys(session, module_id: str) -> set[str]:
    rows = session.execute(
        select(WhitelistEntry.whitelist_key).where(WhitelistEntry.module_id == module_id)
    ).all()
    return {kw[0] for kw in rows}