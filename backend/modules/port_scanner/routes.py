from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from api.envelope import ok
from api.security import ApiError, require_local_token
from core.executor import dispatch_scan
from core.module_registry import discover_modules
from storage.db import Scan, ScanItem, WhitelistEntry, db, dt_to_iso

MODULE_ID = "port-scanner"


class WhitelistIn(BaseModel):
    whitelist_key: str
    label: str | None = None


router = APIRouter(
    prefix="/api/v1/modules/port-scanner",
    tags=["port-scanner"],
    dependencies=[Depends(require_local_token)],
)


def _require_module():
    registry = discover_modules()
    if MODULE_ID not in registry:
        raise ApiError("MODULE_NOT_FOUND", "Module port-scanner chưa được đăng ký.", status_code=404)
    return registry[MODULE_ID]


@router.post("/scan")
async def start_scan() -> dict:
    """Bắt đầu 1 lượt quét mới — trả scan_id ngay, kết quả đẩy qua WebSocket."""
    manifest = _require_module()
    scan_id = await dispatch_scan(manifest)
    return ok({"scan_id": scan_id})


@router.get("/scans/latest")
async def latest_scan() -> dict:
    """Kết quả lượt quét gần nhất — render dashboard khi mới load trang."""
    with db.session() as s:
        row = s.execute(
            select(Scan)
            .where(Scan.module_id == MODULE_ID)
            .order_by(Scan.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return ok(None)
        data = _scan_to_dict(s, row)
    return ok(data)


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict:
    with db.session() as s:
        row = s.get(Scan, scan_id)
        if row is None or row.module_id != MODULE_ID:
            raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy lượt quét.", status_code=404)
        data = _scan_to_dict(s, row)
    return ok(data)


@router.get("/scans")
async def list_scans(page: int = 1, page_size: int = 20) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    with db.session() as s:
        total = s.execute(
            select(func.count()).select_from(Scan).where(Scan.module_id == MODULE_ID)
        ).scalar_one()
        rows = s.execute(
            select(Scan)
            .where(Scan.module_id == MODULE_ID)
            .order_by(Scan.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        items = [_scan_summary(r) for r in rows]
    return ok({"items": items, "page": page, "page_size": page_size, "total": total})


@router.get("/whitelist")
async def list_whitelist() -> dict:
    with db.session() as s:
        rows = s.execute(
            select(WhitelistEntry)
            .where(WhitelistEntry.module_id == MODULE_ID)
            .order_by(WhitelistEntry.created_at.desc())
        ).scalars().all()
        data = [
            {
                "id": w.id,
                "module_id": w.module_id,
                "whitelist_key": w.whitelist_key,
                "label": w.label,
                "created_at": dt_to_iso(w.created_at),
            }
            for w in rows
        ]
    return ok(data)


@router.post("/whitelist")
async def add_whitelist(payload: WhitelistIn) -> dict:
    key = payload.whitelist_key.strip()
    if not key:
        raise ApiError("VALIDATION_ERROR", "whitelist_key không được để trống.")
    with db.session() as s:
        existing = s.execute(
            select(WhitelistEntry).where(
                WhitelistEntry.module_id == MODULE_ID,
                WhitelistEntry.whitelist_key == key,
            )
        ).scalar_one_or_none()
        if existing:
            return ok({"id": existing.id, "created": False})
        entry = WhitelistEntry(
            module_id=MODULE_ID,
            whitelist_key=key,
            label=(payload.label or "").strip() or None,
        )
        s.add(entry)
        s.commit()
        return ok({"id": entry.id, "created": True})


@router.delete("/whitelist/{entry_id}")
async def remove_whitelist(entry_id: int) -> dict:
    with db.session() as s:
        entry = s.get(WhitelistEntry, entry_id)
        if entry is None or entry.module_id != MODULE_ID:
            raise ApiError("WHITELIST_NOT_FOUND", "Mục whitelist không tồn tại.", status_code=404)
        s.delete(entry)
        s.commit()
    return ok({"id": entry_id, "deleted": True})


# ------------------------------------------------------------------ helpers
def _scan_summary(row: Scan) -> dict:
    import json

    return {
        "id": row.id,
        "status": row.status,
        "started_at": dt_to_iso(row.started_at),
        "finished_at": dt_to_iso(row.finished_at),
        "summary": json.loads(row.summary_json) if row.summary_json else {},
        "partial_result": row.partial_result,
        "error_message": row.error_message,
    }


def _scan_to_dict(session, row: Scan) -> dict:
    import json

    severity_rank = {"danger": 0, "warning": 1, "safe": 2}
    item_rows = session.execute(
        select(ScanItem).where(ScanItem.scan_id == row.id)
    ).scalars().all()
    item_rows.sort(key=lambda it: severity_rank.get(it.severity, 9))
    items = [
        {
            "id": it.id,
            "severity": it.severity,
            "title": it.title,
            "detail": json.loads(it.detail_json) if it.detail_json else {},
            "whitelist_key": it.whitelist_key,
            "is_new": it.is_new,
        }
        for it in item_rows
    ]
    data = _scan_summary(row)
    data["items"] = items
    return data