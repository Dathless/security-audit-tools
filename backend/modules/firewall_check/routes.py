from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from api.envelope import ok
from api.scan_results import scan_summary, scan_to_dict
from api.security import ApiError, require_local_token
from core.executor import dispatch_scan
from core.module_registry import discover_modules
from core.scanner_base import ScanError
from storage.db import Scan, db

MODULE_ID = "firewall-check"


router = APIRouter(
    prefix="/api/v1/modules/firewall-check",
    tags=["firewall-check"],
    dependencies=[Depends(require_local_token)],
)


def _require_module():
    registry = discover_modules()
    if MODULE_ID not in registry:
        raise ApiError("MODULE_NOT_FOUND", "Module firewall-check chưa được đăng ký.", status_code=404)
    return registry[MODULE_ID]


@router.post("/scan", responses={409: {"description": "A Firewall scan is already running"}})
async def start_scan() -> dict:
    """Read Windows Firewall in the background; return scan_id immediately.

    Progress and terminal done/error events use /ws/scan/{scan_id}.
    No firewall settings are modified. Missing permissions, unsupported Windows
    commands, a 60-second timeout or invalid data fail the scan, not an empty pass.
    """
    manifest = _require_module()
    try:
        scan_id = await dispatch_scan(manifest)
    except ScanError as exc:
        raise ApiError(exc.code, exc.message, status_code=409) from exc
    return ok({"scan_id": scan_id})


@router.get("/scans/latest")
async def latest_scan() -> dict:
    """Return the latest firewall scan, including errors/running state, or null.

    Summary: total_profiles, total_rules, danger, warning, safe. Items contain
    profile/rule evidence, reason codes and manual review guidance.
    """
    with db.session() as s:
        row = s.execute(
            select(Scan)
            .where(Scan.module_id == MODULE_ID)
            .order_by(Scan.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return ok(None)
        data = scan_to_dict(s, row)
    return ok(data)


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict:
    """Return a firewall scan with items; missing or other-module IDs return 404."""
    with db.session() as s:
        row = s.get(Scan, scan_id)
        if row is None or row.module_id != MODULE_ID:
            raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy lượt quét.", status_code=404)
        data = scan_to_dict(s, row)
    return ok(data)


@router.get("/scans")
async def list_scans(page: int = 1, page_size: int = 20) -> dict:
    """List firewall scan summaries, newest first; page >= 1, page_size 1..100."""
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
        items = [scan_summary(r) for r in rows]
    return ok({"items": items, "page": page, "page_size": page_size, "total": total})
