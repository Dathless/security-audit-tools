from __future__ import annotations

from sqlalchemy import select

from helpers import fake_conn
from storage.db import Scan, ScanItem, db


async def test_scan_error_sets_error_state(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-001: Scanner ném ScanError -> DB status=error, error_message=msg."""
    from core import executor as executor_mod
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("SCAN_PERMISSION_DENIED", "cannot read connections")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-state-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "error"
        assert "cannot read" in row.error_message


async def test_generic_exception_sets_scan_failed(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-002: Scanner ném RuntimeError -> DB status=error, error_message chứa 'boom'."""
    from core import executor as executor_mod
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-gen-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status == "error"
        assert "boom" in row.error_message


async def test_scan_error_publishes_ws_event(patch_psutil, port_manifest, monkeypatch, event_collector):
    """CL-ERR-003: ScanError -> event_bus publish {type:error, code:CODE}."""
    from core import executor as executor_mod
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("SCAN_TIMEOUT", "timed out")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-evt-1")

    errors = [msg for topic, msg in event_collector if topic.endswith(".error")]
    assert len(errors) == 1
    assert errors[0]["type"] == "error"
    assert errors[0]["code"] == "SCAN_TIMEOUT"


async def test_generic_exception_publishes_scan_failed(patch_psutil, port_manifest, monkeypatch, event_collector):
    """CL-ERR-004: RuntimeError -> event có code=SCAN_FAILED."""
    from core import executor as executor_mod
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise RuntimeError("disk full")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-evt-2")

    errors = [msg for topic, msg in event_collector if topic.endswith(".error")]
    assert len(errors) == 1
    assert errors[0]["code"] == "SCAN_FAILED"


async def test_error_scan_no_items_in_db(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-005: Scanner fail -> scan_items rỗng (không persist item nào)."""
    from core import executor as executor_mod
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("ERR", "fail")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-noitem-1")

    with db.session() as s:
        items = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id)).all()
        assert items == []


async def test_error_scan_no_summary(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-006: Scanner fail -> summary_json = None."""
    from core import executor as executor_mod
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("ERR", "fail")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-nosum-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.summary_json is None


async def test_error_scan_does_not_crash_app(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-008: Gọi execute_scan với scanner lỗi -> không có exception thoát ra ngoài."""
    from core import executor as executor_mod
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("ERR", "fail")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    patch_psutil([])
    result = await executor_mod.execute_scan(port_manifest, "err-nocrash-1")
    assert result == "err-nocrash-1"


async def test_error_scan_status_error(patch_psutil, port_manifest, monkeypatch):
    """CL-ERR-007: Lỗi DB khi persist -> rollback, status vẫn error hoặc running."""
    from core import executor as executor_mod
    from modules.port_scanner.scanner import PortScannerModule
    from core.event_bus import event_bus

    async def _boom_publish(topic, message):
        if topic.endswith(".item"):
            raise RuntimeError("db commit fail")

    async def _run(self, progress_cb=None):
        pass

    monkeypatch.setattr(PortScannerModule, "run", _run)
    monkeypatch.setattr(event_bus, "publish", _boom_publish)
    patch_psutil([fake_conn("127.0.0.1", 80)])
    scan_id = await executor_mod.execute_scan(port_manifest, "err-db-1")

    with db.session() as s:
        row = s.get(Scan, scan_id)
        assert row.status in ("error", "running")
