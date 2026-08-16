from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from helpers import fake_conn, fake_process
from storage.db import Scan, ScanDiffLog, ScanItem, WhitelistEntry, db


async def test_scan_lifecycle(client, patch_psutil, port_manifest):
    """TC-SCAN-004: lifecycle scan — record running -> done, result persist, truy vấn lại."""
    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(
            Scan(
                id=scan_id,
                module_id="port-scanner",
                status="running",
                started_at=datetime.utcnow(),
            )
        )
        s.commit()

    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 4444)])
    assert await execute_scan(port_manifest, scan_id) == scan_id

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "done"
        assert row.finished_at is not None
        assert "danger" in row.summary_json
        assert row.partial_result is False

    resp = client.get(f"/api/v1/modules/port-scanner/scans/{scan_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "done"
    assert data["items"][0]["severity"] == "danger"
    assert data["items"][0]["whitelist_key"] == "4444"


# ---------------------------------------------------------------------------
# DIFFING (TC-DIFF)
# ---------------------------------------------------------------------------


async def test_diff_identical_consecutive_scans(patch_psutil, port_manifest):
    """TC-DIFF-002: hai scan giống hệt -> scan 2 không có appeared/disappeared, item không new."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80), fake_conn("127.0.0.1", 443)])
    await execute_scan(port_manifest, "diff-s1")
    await execute_scan(port_manifest, "diff-s2")

    with db.session() as s:
        s2_items = s.scalars(select(ScanItem).where(ScanItem.scan_id == "diff-s2")).all()
        assert len(s2_items) == 2
        assert all(not it.is_new for it in s2_items)
        logs = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "diff-s2")).all()
        assert logs == []


_DIFF_CASES = [
    # (scan1 ports, scan2 ports, appeared@scan2, disappeared@scan2)
    ([80, 443], [80, 443], [], []),  # Case A: identical
    ([80], [80, 443], [443], []),  # Case B: new
    ([80, 443], [80], [], [443]),  # Case C: disappeared
    ([], [80], [80], []),  # Case D: empty -> new
]


@pytest.mark.parametrize("c1,c2,appeared,disappeared", _DIFF_CASES)
async def test_diff_fixture_matrix(clean_db, patch_psutil, port_manifest, c1, c2, appeared, disappeared):
    """TC-DIFF-001/003/004/005: ma trận diff (mục 24) + persistence scan_diff_log.

    Mỗi case chạy trên DB sạch riêng (clean_db) để diff không bị nhiễu bởi case trước.
    """
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", p) for p in c1])
    s1 = "mx-s-1"
    await execute_scan(port_manifest, s1)
    patch_psutil([fake_conn("127.0.0.1", p) for p in c2])
    s2 = "mx-s-2"
    await execute_scan(port_manifest, s2)

    with db.session() as s:
        logs2 = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == s2)).all()
        assert sorted((l.whitelist_key for l in logs2 if l.change_type == "appeared"), key=int) == [
            str(p) for p in sorted(appeared)
        ]
        assert sorted((l.whitelist_key for l in logs2 if l.change_type == "disappeared"), key=int) == [
            str(p) for p in sorted(disappeared)
        ]
        assert all(l.scan_id == s2 for l in logs2)
        # scan đầu tiên: mọi mục đều là appeared (TC-DIFF-001)
        logs1 = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == s1)).all()
        assert sorted((l.whitelist_key for l in logs1), key=int) == [str(p) for p in sorted(c1)]


# ---------------------------------------------------------------------------
# WHITELIST (TC-WL)
# ---------------------------------------------------------------------------


async def test_whitelist_override_severity_via_api(client, patch_psutil, port_manifest):
    """TC-WL-007: whitelist (tạo qua API) override danger -> safe khi scan lại."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 4444, pid=42)], {42: fake_process("bad.exe")})
    scan_id = await execute_scan(port_manifest, "wl-api-1")
    with db.session() as s:
        item = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id)).one()
        assert item.severity == "danger"
        assert item.whitelist_key == "4444:bad.exe"

    resp = client.post(
        "/api/v1/modules/port-scanner/whitelist",
        json={"whitelist_key": "4444:bad.exe", "label": "app hợp lệ"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["created"] is True

    patch_psutil([fake_conn("127.0.0.1", 4444, pid=42)], {42: fake_process("bad.exe")})
    scan_id2 = await execute_scan(port_manifest, "wl-api-2")
    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id2)).one()
        assert item2.severity == "safe"


# ---------------------------------------------------------------------------
# DB INTEGRITY (TC-DB)
# ---------------------------------------------------------------------------


def test_whitelist_db_uniqueness(client):
    """TC-DB-004: DB constraint (module_id, whitelist_key) chặn duplicate."""
    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="445:x"))
        s.commit()
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="445:x"))
            s.commit()


async def test_transaction_rollback_on_persist_failure(patch_psutil, port_manifest, monkeypatch):
    """TC-DB-005: lỗi giữa lúc persist -> rollback, không có scan item mồ côi."""
    from core import executor as executor_mod
    from core.event_bus import event_bus

    async def _boom(topic, message):
        if topic.endswith(".item"):
            raise RuntimeError("publish item fail")

    monkeypatch.setattr(event_bus, "publish", _boom)
    patch_psutil([fake_conn("127.0.0.1", 4444)])
    scan_id = await executor_mod.execute_scan(port_manifest, "rollback-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "error"
        assert row.error_message
        assert row.summary_json is None
        n_items = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id)).all()
        assert n_items == []


# ---------------------------------------------------------------------------
# ERROR HANDLING (TC-ERR)
# ---------------------------------------------------------------------------


async def test_scanner_exception_error_state(patch_psutil, port_manifest, monkeypatch, event_collector):
    """TC-ERR-001: scanner raise -> scan error state + error event qua event bus."""
    from core import executor as executor_mod
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise executor_mod.ScanError("SCAN_PERMISSION_DENIED", "cannot read connections")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    scan_id = await executor_mod.execute_scan(port_manifest, "err-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "error"
        assert row.error_message  # message được lưu; code chỉ xuất hiện trong event
        assert "cannot read" in row.error_message

    errors = [msg for topic, msg in event_collector if topic == f"scan.{scan_id}.error"]
    assert len(errors) == 1
    assert errors[0]["type"] == "error"
    assert errors[0]["code"] == "SCAN_PERMISSION_DENIED"


def test_db_unavailable_error_envelope(client_no_raise, monkeypatch):
    """TC-ERR-002: DB fail -> error rõ ràng, không leak stack trace."""
    from storage.db import db

    class _BrokenSession:
        def __enter__(self):
            raise RuntimeError("db is down")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(db, "session", lambda: _BrokenSession())
    resp = client_no_raise.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in resp.text
    assert "db is down" not in resp.text


# ---------------------------------------------------------------------------
# DIFF EDGE CASES (CL-DIFF-005..008)
# ---------------------------------------------------------------------------


async def test_diff_mix_appeared_and_disappeared(patch_psutil, port_manifest):
    """CL-DIFF-005: Scan #1={80,443} -> Scan #2={80,8080} -> 443 disappeared, 8080 appeared."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80), fake_conn("127.0.0.1", 443)])
    await execute_scan(port_manifest, "diff-mix-1")

    patch_psutil([fake_conn("127.0.0.1", 80), fake_conn("127.0.0.1", 8080)])
    await execute_scan(port_manifest, "diff-mix-2")

    with db.session() as s:
        logs = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "diff-mix-2")).all()
        appeared = sorted([l.whitelist_key for l in logs if l.change_type == "appeared"], key=int)
        disappeared = sorted([l.whitelist_key for l in logs if l.change_type == "disappeared"], key=int)
        assert appeared == ["8080"]
        assert disappeared == ["443"]


async def test_diff_is_new_flag(patch_psutil, port_manifest):
    """CL-DIFF-006: Scan #2 có port mới -> is_new=True cho port đó, is_new=False cho port cũ."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "diff-new-1")

    patch_psutil([fake_conn("127.0.0.1", 80), fake_conn("127.0.0.1", 443)])
    await execute_scan(port_manifest, "diff-new-2")

    with db.session() as s:
        items = s.scalars(select(ScanItem).where(ScanItem.scan_id == "diff-new-2")).all()
        by_key = {it.whitelist_key: it.is_new for it in items}
        assert by_key["80"] is False
        assert by_key["443"] is True


async def test_diff_log_scan_id_is_current(patch_psutil, port_manifest):
    """CL-DIFF-007: Diff log entry có scan_id = scan hiện tại."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "diff-sid-1")

    patch_psutil([fake_conn("127.0.0.1", 443)])
    await execute_scan(port_manifest, "diff-sid-2")

    with db.session() as s:
        logs = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "diff-sid-2")).all()
        assert all(l.scan_id == "diff-sid-2" for l in logs)


async def test_diff_across_three_scans(patch_psutil, port_manifest):
    """CL-DIFF-008: Scan #1={80} -> #2={80,443} -> #3={80} -> log appeared(#2) + disappeared(#3)."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "diff-3s-1")

    patch_psutil([fake_conn("127.0.0.1", 80), fake_conn("127.0.0.1", 443)])
    await execute_scan(port_manifest, "diff-3s-2")

    patch_psutil([fake_conn("127.0.0.1", 80)])
    await execute_scan(port_manifest, "diff-3s-3")

    with db.session() as s:
        logs2 = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "diff-3s-2")).all()
        appeared2 = sorted([l.whitelist_key for l in logs2 if l.change_type == "appeared"], key=int)
        assert appeared2 == ["443"]

        logs3 = s.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "diff-3s-3")).all()
        disappeared3 = sorted([l.whitelist_key for l in logs3 if l.change_type == "disappeared"], key=int)
        assert disappeared3 == ["443"]


async def test_concurrent_scans_allowed(patch_psutil, port_manifest, monkeypatch):
    """TC-ERR-004: hai scan gần đồng thời -> chạy song song, cả hai đều done."""
    from core.executor import dispatch_scan

    patch_psutil([fake_conn("127.0.0.1", 8080)])

    spawned: list = []
    orig_create_task = asyncio.create_task

    def _spy(coro, *args, **kwargs):
        task = orig_create_task(coro, *args, **kwargs)
        spawned.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _spy)

    id1 = await dispatch_scan(port_manifest)
    id2 = await dispatch_scan(port_manifest)
    assert id1 != id2

    with db.session() as s:
        rows = s.execute(select(Scan).where(Scan.id.in_([id1, id2]))).scalars().all()
        assert len(rows) == 2
        assert all(r.status == "running" for r in rows)

    await asyncio.gather(*spawned)

    with db.session() as s:
        rows = s.execute(select(Scan).where(Scan.id.in_([id1, id2]))).scalars().all()
        assert all(r.status == "done" for r in rows)
