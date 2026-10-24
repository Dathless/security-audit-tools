from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from api.envelope import ok
from api.security import require_local_token
from core.config import config
from core.module_registry import discover_modules
from storage.db import Scan, db, dt_to_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_local_token)])


@router.get("/modules")
async def list_modules() -> dict:
    """Danh sách module đã đăng ký — nguồn cho sidebar của frontend."""
    registry = discover_modules()
    result = []
    with db.session() as s:
        for module_id, manifest in registry.items():
            if not config.module(module_id).enabled:
                continue
            last = s.execute(
                select(Scan)
                .where(Scan.module_id == module_id, Scan.status != "running")
                .order_by(Scan.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            last_scan = None
            if last:
                serializer = manifest.meta.get("summary_serializer")
                last_scan = {
                    "id": last.id,
                    "status": last.status,
                    "started_at": dt_to_iso(last.started_at),
                    "finished_at": dt_to_iso(last.finished_at),
                    "summary": serializer(s, last) if serializer else _load_json(last.summary_json),
                    "partial_result": last.partial_result,
                }
            result.append(
                {
                    "id": manifest.id,
                    "display_name": manifest.display_name,
                    "version": manifest.version,
                    "enabled": True,
                    "status": "active",
                    "has_scan": last is not None,
                    "last_scan": last_scan,
                }
            )
    return ok({"modules": result})


@router.get("/health")
async def health() -> dict:
    """Health check — UI hiển thị trạng thái Idle/Scanning ở sidebar footer."""
    with db.session() as s:
        running_count = s.execute(
            select(func.count()).select_from(Scan).where(Scan.status == "running")
        ).scalar_one()
    return ok(
        {
            "status": "scanning" if running_count else "idle",
            "running_scans": running_count,
            "registered_modules": len(discover_modules()),
            "uptime_seconds": _uptime_seconds(),
        }
    )


_started_at = datetime.utcnow()


def _uptime_seconds() -> int:
    return int((datetime.utcnow() - _started_at).total_seconds())


def _load_json(text: str | None) -> dict | None:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
