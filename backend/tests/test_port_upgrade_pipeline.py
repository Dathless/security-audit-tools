from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from core.module_registry import ModuleManifest
from core.scanner_base import ScanError, ScanResult, ScanResultItem, ScannerBase
from storage.db import Scan, ScanDiffLog, ScanItem, WhitelistEntry, db


class SnapshotScanner(ScannerBase):
    partial = False
    version = 2
    fail_persist = False

    async def run(self, progress_cb=None):
        return ScanResult(module_id="test-port-v2", started_at="", finished_at="",
                          items=[ScanResultItem(severity="warning", title="current", detail={"key": "current"})],
                          summary={"identity_version": self.version, "danger": 0, "warning": 1, "safe": 0},
                          partial_result=self.partial)

    def get_whitelist_key(self, item):
        return item.detail["key"]

    def on_persist(self, session, scan_id, result, previous):
        if self.fail_persist:
            raise RuntimeError("persistence failure")


def manifest():
    return ModuleManifest(id="test-port-v2", display_name="test", version="2", scanner_cls=SnapshotScanner,
                          meta={"identity_version": 2, "serialize_scans": True, "whitelist_override": False})


def seed_previous(version=2):
    with db.session() as session:
        session.add(Scan(id="previous", module_id="test-port-v2", status="done", started_at=datetime(2020, 1, 1),
                         partial_result=False, summary_json='{"identity_version":' + str(version) + '}'))
        session.add(ScanItem(scan_id="previous", module_id="test-port-v2", whitelist_key="gone",
                             severity="safe", title="old", detail_json="{}"))
        session.commit()


async def test_partial_inventory_does_not_claim_disappearance(clean_db, monkeypatch):
    from core.executor import execute_scan
    seed_previous()
    monkeypatch.setattr(SnapshotScanner, "partial", True)
    await execute_scan(manifest(), "partial")
    with db.session() as session:
        assert not session.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "partial", ScanDiffLog.change_type == "disappeared")).all()
    monkeypatch.setattr(SnapshotScanner, "partial", False)
    await execute_scan(manifest(), "next-complete")
    with db.session() as session:
        import json
        assert json.loads(session.get(Scan, "next-complete").summary_json)["baseline_scan_id"] == "previous"


async def test_version_transition_has_initial_baseline_without_false_removal(clean_db):
    from core.executor import execute_scan
    seed_previous(version=1)
    await execute_scan(manifest(), "new-version")
    with db.session() as session:
        assert not session.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "new-version", ScanDiffLog.change_type == "disappeared")).all()


async def test_review_module_preserves_risk_even_if_legacy_key_matches(clean_db):
    from core.executor import execute_scan
    with db.session() as session:
        session.add(WhitelistEntry(module_id="test-port-v2", whitelist_key="current"))
        session.commit()
    await execute_scan(manifest(), "risk")
    with db.session() as session:
        assert session.scalars(select(ScanItem).where(ScanItem.scan_id == "risk")).one().severity == "warning"


async def test_persistence_hook_failure_rolls_back_items_and_diff(clean_db, monkeypatch):
    from core.executor import execute_scan
    monkeypatch.setattr(SnapshotScanner, "fail_persist", True)
    await execute_scan(manifest(), "rollback")
    with db.session() as session:
        assert session.get(Scan, "rollback").status == "error"
        assert not session.scalars(select(ScanItem).where(ScanItem.scan_id == "rollback")).all()
        assert not session.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "rollback")).all()


async def test_constructor_failure_finishes_running_scan(clean_db):
    from core.executor import execute_scan
    class InvalidScanner(SnapshotScanner):
        def __init__(self):
            raise ScanError("SCAN_CONFIG_INVALID", "invalid configuration")
    module = manifest()
    module.scanner_cls = InvalidScanner
    await execute_scan(module, "invalid")
    with db.session() as session:
        assert session.get(Scan, "invalid").status == "error"


async def test_dispatch_rejects_overlap_and_allows_retry_after_failure(clean_db, monkeypatch):
    from core.executor import dispatch_scan, execute_scan
    monkeypatch.setattr("core.executor.asyncio.create_task", lambda coroutine: coroutine.close())
    module = manifest()
    scan_id = await dispatch_scan(module)
    with pytest.raises(ScanError) as error:
        await dispatch_scan(module)
    assert error.value.code == "SCAN_ALREADY_RUNNING"
    with db.session() as session:
        session.get(Scan, scan_id).status = "error"
        session.commit()
    assert await dispatch_scan(module) != scan_id


def test_restart_recovers_only_serialized_modules(clean_db):
    from core.executor import recover_abandoned_scans
    with db.session() as session:
        for key in ("test-port-v2", "other"):
            session.add(Scan(id=key, module_id=key, status="running", started_at=datetime.utcnow()))
        session.commit()
    recover_abandoned_scans({"test-port-v2": manifest()})
    with db.session() as session:
        assert session.get(Scan, "test-port-v2").status == "error"
        assert session.get(Scan, "other").status == "running"


async def test_scheduler_skips_only_busy_scan(monkeypatch):
    from core.scheduler import _scheduled_scan_job
    async def busy(_):
        raise ScanError("SCAN_ALREADY_RUNNING", "busy")
    monkeypatch.setattr("core.executor.dispatch_scan", busy)
    await _scheduled_scan_job(manifest())


async def test_cancellation_finishes_running_scan_and_propagates(clean_db):
    import asyncio
    from core.executor import execute_scan
    started = asyncio.Event()
    class WaitingScanner(SnapshotScanner):
        async def run(self, progress_cb=None):
            started.set()
            await asyncio.Event().wait()
    module = manifest()
    module.scanner_cls = WaitingScanner
    task = asyncio.create_task(execute_scan(module, "cancelled"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with db.session() as session:
        assert session.get(Scan, "cancelled").status == "error"


async def test_item_events_observe_committed_snapshot(clean_db):
    import asyncio
    from core.event_bus import event_bus
    from core.executor import execute_scan
    observed = []
    async def read_snapshot(topic, message):
        with db.session() as session:
            row = session.get(Scan, "committed")
            items = list(session.scalars(select(ScanItem).where(ScanItem.scan_id == row.id)))
            observed.append((row.status, len(items)))
        await asyncio.sleep(0)
        with db.session() as session:
            session.add(WhitelistEntry(module_id="other", whitelist_key="subscriber-write"))
            session.commit()
    unsubscribe = event_bus.subscribe("scan.committed.item", read_snapshot)
    try:
        await execute_scan(manifest(), "committed")
    finally:
        unsubscribe()
    assert observed == [("done", 1)]
    with db.session() as session:
        assert session.scalar(select(WhitelistEntry).where(WhitelistEntry.module_id == "other")) is not None
