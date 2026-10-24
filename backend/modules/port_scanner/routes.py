from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy import func, select

from api.envelope import ok
from api.scan_results import scan_summary
from api.security import ApiError, require_local_token
from core.executor import dispatch_scan
from core.module_registry import discover_modules
from core.scanner_base import ScanError
from storage.db import Scan, ScanItem, WhitelistEntry, db, dt_to_iso
from .evidence import complete_identity, endpoint_key, review_fingerprint
from .models import PortReview
from .reviews import port_scan_to_dict, review_to_dict
import json

MODULE_ID = "port-scanner"


class WhitelistIn(BaseModel):
    whitelist_key: str
    label: str | None = None


router = APIRouter(
    prefix="/api/v1/modules/port-scanner",
    tags=["port-scanner"],
    dependencies=[Depends(require_local_token)],
    responses={401: {"description": "Local token missing or invalid"}},
)


def _require_module():
    registry = discover_modules()
    if MODULE_ID not in registry:
        raise ApiError("MODULE_NOT_FOUND", "Module port-scanner chưa được đăng ký.", status_code=404)
    return registry[MODULE_ID]


@router.post("/scan", responses={409: {"description": "A Port scan is already running"}})
async def start_scan() -> dict:
    """Bắt đầu 1 lượt quét mới — trả scan_id ngay, kết quả đẩy qua WebSocket."""
    manifest = _require_module()
    try:
        scan_id = await dispatch_scan(manifest)
    except ScanError as exc:
        raise ApiError(exc.code, exc.message, status_code=409) from exc
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
        data = port_scan_to_dict(s, row)
    return ok(data)


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict:
    with db.session() as s:
        row = s.get(Scan, scan_id)
        if row is None or row.module_id != MODULE_ID:
            raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy lượt quét.", status_code=404)
        data = port_scan_to_dict(s, row)
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
        items = [scan_summary(r) for r in rows]
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


@router.post("/whitelist", deprecated=True, responses={410: {"description": "Retired; use POST /reviews with scan_id and item_id"}})
async def add_whitelist(payload: WhitelistIn) -> dict:
    """Retired: use POST /reviews; acknowledgements never lower raw risk."""
    raise ApiError("WHITELIST_REPLACED_BY_REVIEW", "Dùng POST /reviews với scan_id và item_id; xác nhận không đổi mức rủi ro.", status_code=410)


@router.delete("/whitelist/{entry_id}")
async def remove_whitelist(entry_id: int) -> dict:
    with db.session() as s:
        entry = s.get(WhitelistEntry, entry_id)
        if entry is None or entry.module_id != MODULE_ID:
            raise ApiError("WHITELIST_NOT_FOUND", "Mục whitelist không tồn tại.", status_code=404)
        s.delete(entry)
        s.commit()
    return ok({"id": entry_id, "deleted": True})


class ReviewIn(BaseModel):
    scan_id: str = Field(min_length=1)
    item_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


@router.post("/reviews", responses={404: {"description": "Item not found in this module/snapshot"}, 409: {"description": "Target snapshot is stale, running or legacy"}})
async def add_review(payload: ReviewIn) -> dict:
    """Acknowledge current persisted evidence; stale targets return 409.

    Complete owners allow persistence until observed evidence changes. Missing
    metadata/partial inventory restrict acknowledgement to this scan. Risk is
    never overwritten. Repeated requests for the same evidence are idempotent.
    """
    with db.session() as session:
        scan = session.get(Scan, payload.scan_id)
        item = session.get(ScanItem, payload.item_id)
        if not scan or scan.module_id != MODULE_ID or not item or item.scan_id != scan.id or item.module_id != MODULE_ID:
            raise ApiError("SCAN_ITEM_NOT_FOUND", "Không tìm thấy endpoint trong lượt quét.", 404)
        latest = session.scalar(select(Scan).where(Scan.module_id == MODULE_ID).order_by(Scan.started_at.desc()).limit(1))
        if scan.status != "done" or latest.id != scan.id or json.loads(scan.summary_json or "{}").get("identity_version") != 2:
            raise ApiError("REVIEW_TARGET_STALE", "Tải lượt quét mới nhất trước khi xác nhận endpoint.", 409)
        detail = json.loads(item.detail_json)
        fingerprint = review_fingerprint(detail, item.severity)
        scope = "persistent" if complete_identity(detail) and not scan.partial_result else "scan"
        key = fingerprint if scope == "persistent" else fingerprint + ":" + scan.id
        record = session.scalar(select(PortReview).where(PortReview.review_key == key))
        created = record is None
        if record is None:
            record = PortReview(review_key=key, endpoint_key=endpoint_key(detail), fingerprint=fingerprint,
                                scan_id=scan.id, scope=scope)
            session.add(record)
        if created or record.expired_at is not None:
            record.scan_id = scan.id
            record.note = (payload.note or "").strip() or None
            record.reviewed_at = datetime.utcnow()
            record.expired_at = None
        session.commit()
        return ok({**review_to_dict(record), "created": created})


@router.get("/reviews")
async def list_reviews(page: int = 1, page_size: int = 20) -> dict:
    """List stored acknowledgements, including expiry; page size capped at 100."""
    page, page_size = max(page, 1), min(max(page_size, 1), 100)
    with db.session() as session:
        total = session.scalar(select(func.count()).select_from(PortReview))
        rows = session.scalars(select(PortReview).order_by(PortReview.reviewed_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return ok({"items": [review_to_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total})


@router.delete("/reviews/{review_id}", responses={404: {"description": "Review not found"}})
async def remove_review(review_id: int) -> dict:
    with db.session() as session:
        record = session.get(PortReview, review_id)
        if record is None:
            raise ApiError("REVIEW_NOT_FOUND", "Không tìm thấy xác nhận.", 404)
        session.delete(record)
        session.commit()
    return ok({"id": review_id, "deleted": True})
