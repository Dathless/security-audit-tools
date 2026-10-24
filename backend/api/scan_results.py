from __future__ import annotations

from sqlalchemy import select

from storage.db import Scan, ScanItem, dt_to_iso


# ------------------------------------------------------------------ helpers
def scan_summary(row: Scan) -> dict:
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


def scan_to_dict(session, row: Scan) -> dict:
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
    data = scan_summary(row)
    data["items"] = items
    return data