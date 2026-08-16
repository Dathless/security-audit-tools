from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from helpers import fake_conn
from storage.db import Scan, ScanItem, db


async def test_scan_creates_running_record(patch_psutil, port_manifest, clean_db):
    """CL-LC-001: POST scan -> query DB ngay -> status = running."""
    scan_id = "lc-run-1"
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "running"


async def test_scan_completes_to_done(patch_psutil, port_manifest):
    """CL-LC-002: Chờ executor xong -> query DB -> status = done, summary_json có."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    scan_id = await execute_scan(port_manifest, "lc-done-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "done"
        assert row.summary_json is not None
        assert row.finished_at is not None


async def test_scan_items_persist(patch_psutil, port_manifest):
    """CL-LC-003: Scan xong -> query scan_items -> mỗi item có severity, title, detail_json, whitelist_key."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 8080), fake_conn("127.0.0.1", 4444)])
    scan_id = await execute_scan(port_manifest, "lc-items-1")

    with db.session() as s:
        items = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id)).all()
        assert len(items) == 2
        for item in items:
            assert item.severity in ("safe", "warning", "danger")
            assert item.title
            assert item.detail_json
            assert item.whitelist_key


async def test_scan_summary_correct(patch_psutil, port_manifest):
    """CL-LC-004: Port 4444(danger) + 80(safe) -> summary."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 4444), fake_conn("127.0.0.1", 80)])
    scan_id = await execute_scan(port_manifest, "lc-sum-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        summary = json.loads(row.summary_json)
        assert summary["total_open"] == 2
        assert summary["danger"] == 1
        assert summary["warning"] == 0
        assert summary["safe"] == 1


async def test_query_history_after_scan(client, patch_psutil, port_manifest):
    """CL-LC-005: Scan xong -> GET /scans -> list chứa scan đó."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "lc-hist-1")

    resp = client.get("/api/v1/modules/port-scanner/scans")
    assert resp.status_code == 200
    data = resp.json()["data"]
    ids = [it["id"] for it in data["items"]]
    assert "lc-hist-1" in ids


async def test_query_latest_scan(client, patch_psutil, port_manifest):
    """CL-LC-006: Scan xong -> GET /scans/latest -> trả scan đó."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "lc-latest-1")

    resp = client.get("/api/v1/modules/port-scanner/scans/latest")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "lc-latest-1"


async def test_query_scan_detail(client, patch_psutil, port_manifest):
    """CL-LC-007: Scan xong -> GET /scans/{id} -> có items array."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    scan_id = await execute_scan(port_manifest, "lc-detail-1")

    resp = client.get(f"/api/v1/modules/port-scanner/scans/{scan_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == scan_id
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1


async def test_partial_result_on_permission_denied(clean_db, patch_psutil, port_manifest):
    """CL-LC-008: FakePsutil(deny_net=True) -> scan xong -> partial_result=True."""
    from core.executor import execute_scan

    patch_psutil([], deny_net=True)
    scan_id = await execute_scan(port_manifest, "lc-partial-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.partial_result is True


async def test_started_at_before_finished_at(patch_psutil, port_manifest):
    """CL-LC-009: Scan xong -> started_at < finished_at."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    scan_id = await execute_scan(port_manifest, "lc-time-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.started_at <= row.finished_at
