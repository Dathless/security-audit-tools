from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from api.scan_results import scan_to_dict
from storage.db import ScanItem, dt_to_iso
from .evidence import complete_identity, endpoint_key, observation_signature, review_fingerprint
from .models import PortReview


def persist_snapshot(session, scan_id, result, previous) -> None:
    before = {}
    if previous:
        for row in session.scalars(select(ScanItem).where(ScanItem.scan_id == previous.id)):
            before[row.whitelist_key] = (json.loads(row.detail_json), row.severity)
    current = {}
    for item in result.items:
        key = endpoint_key(item.detail)
        current[key] = item
        old = before.get(key)
        change = "initial" if previous is None else "added" if old is None else "unchanged"
        if old and observation_signature(old[0], old[1]) != observation_signature(item.detail, item.severity):
            change = "changed"
            item.detail["previous_evidence"] = {"owners": old[0].get("owners", []), "severity": old[1], "reasons": old[0].get("reasons", [])}
        item.detail["change_type"] = change
    result.summary["removed_endpoints"] = [
        {field: before[key][0].get(field) for field in ("protocol", "family", "listener", "port")}
        for key in sorted(before.keys() - current.keys())
    ] if not result.partial_result else []
    now = datetime.utcnow()
    for review in session.scalars(select(PortReview).where(PortReview.expired_at.is_(None))):
        if review.scope == "scan":
            if review.scan_id != scan_id:
                review.expired_at = now
            continue
        item = current.get(review.endpoint_key)
        if (item is None and not result.partial_result) or (item is not None and complete_identity(item.detail) and review_fingerprint(item.detail, item.severity) != review.fingerprint):
            review.expired_at = now


def port_scan_to_dict(session, row) -> dict:
    data = scan_to_dict(session, row)
    if (data.get("summary") or {}).get("identity_version") != 2:
        data["assessment_status"] = "legacy"
        for item in data["items"]:
            item["review_status"] = "legacy"
        return data
    data["assessment_status"] = "current"
    active = list(session.scalars(select(PortReview).where(PortReview.expired_at.is_(None))))
    persistent = {review.fingerprint: review for review in active if review.scope == "persistent"}
    scan_only = {(review.fingerprint, review.scan_id): review for review in active if review.scope == "scan"}
    reviewed = 0
    needs_review = 0
    for item in data["items"]:
        detail = item["detail"]
        fingerprint = review_fingerprint(detail, item["severity"])
        match = scan_only.get((fingerprint, row.id))
        if complete_identity(detail) and not data["partial_result"]:
            match = persistent.get(fingerprint) or match
        needs = not match and (item["severity"] != "safe" or detail.get("change_type") in ("added", "changed"))
        item.update(review_status="reviewed" if match else "needs_review" if needs else "unreviewed",
                    review_scope=match.scope if match else None, review_id=match.id if match else None)
        reviewed += bool(match)
        needs_review += bool(needs)
    data["summary"].update(reviewed_count=reviewed, needs_review_count=needs_review)
    return data


def review_to_dict(review: PortReview) -> dict:
    endpoint = json.loads(review.endpoint_key)
    return {"id": review.id, "endpoint_key": review.endpoint_key,
            "label": f"{endpoint[1].upper()} {endpoint[3]}:{endpoint[4]} ({endpoint[2]})",
            "scan_id": review.scan_id, "scope": review.scope, "note": review.note,
            "reviewed_at": dt_to_iso(review.reviewed_at), "expired_at": dt_to_iso(review.expired_at)}


def port_summary(session, row) -> dict:
    return port_scan_to_dict(session, row)["summary"]
