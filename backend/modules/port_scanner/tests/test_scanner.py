from __future__ import annotations

import socket

from sqlalchemy import select

from storage.db import Scan, ScanDiffLog, ScanItem, WhitelistEntry, db


class FakeConn:
    def __init__(self, ip, port, type, status, pid=None):
        self.laddr = (ip, port)
        self.type = type
        self.status = status
        self.pid = pid


class FakeProcess:
    def __init__(self, name, access_denied=False):
        self._name = name
        self._access_denied = access_denied

    def name(self):
        if self._access_denied:
            raise PermissionError("AccessDenied")
        return self._name


class FakePsutil:
    def __init__(self, conns, proc_map=None):
        self.connections = conns
        self.proc_map = proc_map or {}
        self.CONN_LISTEN = "LISTEN"
        self.AccessDenied = PermissionError
        self.NoSuchProcess = ProcessLookupError
        self.ZombieProcess = ProcessLookupError

    def net_connections(self, kind="inet"):
        return self.connections

    def Process(self, pid):
        proc = self.proc_map.get(pid)
        if proc is not None:
            return proc
        raise self.NoSuchProcess(pid)


def fake_conn(ip, port, pid=None, udp=False):
    return FakeConn(
        ip, port, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM, "LISTEN", pid
    )


def patch_psutil(monkeypatch, conns, proc_map=None):
    fake = FakePsutil(conns, proc_map)
    monkeypatch.setattr("modules.port_scanner.scanner.psutil", fake)
    return fake


def _manifest():
    from core.module_registry import discover_modules

    return discover_modules()["port-scanner"]


# ---------------------------------------------------------------- scanner.run
async def test_run_returns_empty_result(monkeypatch, clean_db):
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil(monkeypatch, [])
    result = await PortScannerModule().run()
    assert result.module_id == "port-scanner"
    assert result.items == []
    assert result.summary["total_open"] == 0
    assert result.partial_result is False


async def test_run_classify_severities(monkeypatch, clean_db):
    from modules.port_scanner.scanner import PortScannerModule

    conns = [
        fake_conn("127.0.0.1", 8080),
        fake_conn("0.0.0.0", 445),
        fake_conn("127.0.0.1", 4444),
    ]
    patch_psutil(monkeypatch, conns)

    result = await PortScannerModule().run()
    by_port = {item.detail["port"]: item.severity for item in result.items}
    assert by_port[4444] == "danger"
    assert by_port[445] == "warning"
    assert by_port[8080] == "safe"
    assert result.summary == {"total_open": 3, "danger": 1, "warning": 1, "safe": 1}


async def test_run_reports_partial_permission_denied(monkeypatch, clean_db):
    from modules.port_scanner.scanner import PortScannerModule

    conns = [fake_conn("127.0.0.1", 9000, pid=9999)]
    patch_psutil(monkeypatch, conns, {9999: FakeProcess("svchost.exe", access_denied=True)})

    result = await PortScannerModule().run()
    assert result.partial_result is True
    item = next(i for i in result.items if i.detail["port"] == 9000)
    assert item.detail["permission_denied"] is True


# ------------------------------------------------------- integration (DB)
async def test_diffing_marks_new_and_disappeared(monkeypatch, clean_db):
    from core.executor import execute_scan

    manifest = _manifest()

    patch_psutil(monkeypatch, [fake_conn("127.0.0.1", 1111)])
    scan1 = await execute_scan(manifest, "scan-1")

    patch_psutil(monkeypatch, [fake_conn("127.0.0.1", 2222)])
    scan2 = await execute_scan(manifest, "scan-2")

    with db.session() as s:
        scan1_items = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan1)).all()
        scan2_items = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan2)).all()
        assert len(scan1_items) == 1
        assert scan1_items[0].is_new is True
        assert len(scan2_items) == 1
        assert scan2_items[0].is_new is True

        logs = s.scalars(select(ScanDiffLog)).all()
        types = {(log.scan_id, log.change_type) for log in logs}
        assert (scan1, "appeared") in types
        assert (scan2, "appeared") in types
        assert (scan2, "disappeared") in types

        scan2_row = s.get(Scan, scan2)
        assert scan2_row.status == "done"
        assert scan2_row.summary_json is not None


async def test_whitelist_overrides_severity(monkeypatch, clean_db):
    from core.executor import execute_scan

    manifest = _manifest()

    patch_psutil(monkeypatch, [fake_conn("0.0.0.0", 445)])
    scan_id = await execute_scan(manifest, "scan-wl")

    with db.session() as s:
        item = s.scalars(select(ScanItem)).one()
        assert item.severity == "warning"

    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="445:fake.exe", label="server"))
        s.commit()

    patch_psutil(monkeypatch, [fake_conn("0.0.0.0", 445, pid=7)], {7: FakeProcess("fake.exe")})
    scan_id2 = await execute_scan(manifest, "scan-wl2")

    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id2)).one()
        assert item2.whitelist_key == "445:fake.exe"
        assert item2.severity == "safe"