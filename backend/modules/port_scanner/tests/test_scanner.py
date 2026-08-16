from __future__ import annotations

import sys
import types

import pytest
from sqlalchemy import select

from helpers import FakeProcess, fake_conn
from modules.port_scanner.scanner import PortScannerModule, _build_summary, _nmap_ports
from storage.db import Scan, ScanDiffLog, ScanItem, WhitelistEntry, db


def _manifest():
    from core.module_registry import discover_modules

    return discover_modules()["port-scanner"]


# ---------------------------------------------------------------- scanner.run
async def test_run_returns_empty_result(clean_db, patch_psutil):
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([])
    result = await PortScannerModule().run()
    assert result.module_id == "port-scanner"
    assert result.items == []
    assert result.summary["total_open"] == 0
    assert result.partial_result is False


async def test_run_classify_severities(clean_db, patch_psutil):
    from modules.port_scanner.scanner import PortScannerModule

    conns = [
        fake_conn("127.0.0.1", 8080),
        fake_conn("0.0.0.0", 445),
        fake_conn("127.0.0.1", 4444),
    ]
    patch_psutil(conns)

    result = await PortScannerModule().run()
    by_port = {item.detail["port"]: item.severity for item in result.items}
    assert by_port[4444] == "danger"
    assert by_port[445] == "warning"
    assert by_port[8080] == "safe"
    assert result.summary == {"total_open": 3, "danger": 1, "warning": 1, "safe": 1}

    # Verify reason codes
    reasons_by_port = {item.detail["port"]: item.detail["reasons"] for item in result.items}
    assert "PORT_IN_RISKY_LIST" in reasons_by_port[4444]
    assert "LISTENING_ON_ALL_INTERFACES" in reasons_by_port[445]
    assert reasons_by_port[8080] == []


async def test_run_reports_partial_permission_denied(clean_db, patch_psutil):
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil(
        [fake_conn("127.0.0.1", 9000, pid=9999)],
        {9999: FakeProcess("svchost.exe", access_denied=True)},
    )

    result = await PortScannerModule().run()
    assert result.partial_result is True
    item = next(i for i in result.items if i.detail["port"] == 9000)
    assert item.detail["permission_denied"] is True


# ------------------------------------------------------------- severity matrix
@pytest.mark.parametrize(
    "ip,port,pid,proc,expected",
    [
        ("127.0.0.1", 8080, None, None, "safe"),  # TC-SCANNER-003 localhost safe
        ("127.0.0.1", 443, None, None, "safe"),
        ("0.0.0.0", 8080, None, None, "warning"),  # TC-SCANNER-004 wildcard bind
        ("::", 8080, None, None, "warning"),
        ("127.0.0.1", 4444, None, None, "danger"),  # TC-SCANNER-005 risky port
        ("127.0.0.1", 1337, None, None, "danger"),
        ("127.0.0.1", 31337, None, None, "danger"),
        ("127.0.0.1", 8080, 5, FakeProcess("app.exe"), "safe"),  # TC-PERM-002
        ("127.0.0.1", 8080, 5, FakeProcess(access_denied=True), "warning"),
    ],
)
async def test_severity_matrix(clean_db, patch_psutil, ip, port, pid, proc, expected):
    """TC-SCANNER-006: ma trận severity (IP type x port x process metadata)."""
    from modules.port_scanner.scanner import PortScannerModule

    proc_map = {pid: proc} if (pid is not None and proc is not None) else {}
    patch_psutil([fake_conn(ip, port, pid=pid)], proc_map)

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    assert result.items[0].severity == expected, f"{ip}:{port} pid={pid} -> {result.items[0].severity}"


async def test_process_does_not_exist_still_returns_item(clean_db, patch_psutil):
    """TC-SCANNER-002: PID không tồn tại -> không crash, item vẫn trả, metadata trống."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", 9000, pid=424242)])

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.detail["pid"] == 424242
    assert item.detail["process_name"] == ""
    assert item.detail["permission_denied"] is False
    assert item.severity == "safe"


async def test_service_port_mismatch(clean_db, patch_psutil):
    """TC-SCANNER-007: port/process mismatch -> WARNING + SERVICE_PORT_MISMATCH."""
    from modules.port_scanner.scanner import PortScannerModule

    # Port 22 with wrong process (not sshd)
    patch_psutil([fake_conn("127.0.0.1", 22, pid=10)], {10: FakeProcess("nginx.exe")})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.severity == "warning"
    assert "SERVICE_PORT_MISMATCH" in item.detail["reasons"]


async def test_service_port_match_no_mismatch(clean_db, patch_psutil):
    """TC-SCANNER-008: port/process match -> no mismatch warning."""
    from modules.port_scanner.scanner import PortScannerModule

    # Port 22 with sshd -> no mismatch
    patch_psutil([fake_conn("127.0.0.1", 22, pid=10)], {10: FakeProcess("sshd.exe")})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert "SERVICE_PORT_MISMATCH" not in item.detail["reasons"]


async def test_risky_port_takes_priority_over_mismatch(clean_db, patch_psutil):
    """TC-SCANNER-009: risky port + mismatch -> DANGER (risky port priority)."""
    from modules.port_scanner.scanner import PortScannerModule

    # Port 4444 with wrong process
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=10)], {10: FakeProcess("nginx.exe")})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.severity == "danger"
    assert "PORT_IN_RISKY_LIST" in item.detail["reasons"]
    assert "SERVICE_PORT_MISMATCH" not in item.detail["reasons"]


async def test_whitelist_key_with_process_name(clean_db, patch_psutil):
    """get_whitelist_key: có process name -> 'port:process'."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", 445, pid=7)], {7: FakeProcess("fake.exe")})

    result = await PortScannerModule().run()
    item = result.items[0]
    key = PortScannerModule().get_whitelist_key(item)
    assert key == "445:fake.exe"


async def test_net_connections_access_denied_returns_partial(clean_db, patch_psutil):
    """TC-PERM-001 (mở rộng): không đọc được danh sách kết nối -> partial_result + warning."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([], deny_net=True)

    result = await PortScannerModule().run()
    assert result.partial_result is True
    assert len(result.items) == 1
    assert result.items[0].detail["permission_denied"] is True
    assert result.items[0].severity == "warning"


# ---------------------------------------------------------------------- nmap
async def test_nmap_unavailable_falls_back_to_socket(clean_db, patch_psutil, monkeypatch):
    """TC-NMAP-003: nmap không cài -> fallback socket, scan vẫn thành công."""
    from modules.port_scanner.scanner import PortScannerModule

    monkeypatch.setattr("modules.port_scanner.scanner.shutil.which", lambda _: None)
    patch_psutil([fake_conn("127.0.0.1", 8080)])

    scanner = PortScannerModule()
    scanner.scan_mode = "nmap"
    result = await scanner.run()
    assert len(result.items) == 1
    assert result.items[0].detail["port"] == 8080


async def test_nmap_execution_failure_falls_back_to_socket(clean_db, patch_psutil, monkeypatch):
    """TC-NMAP-004: nmap tồn tại nhưng command fail -> fallback socket."""
    from modules.port_scanner.scanner import PortScannerModule

    monkeypatch.setattr("modules.port_scanner.scanner.shutil.which", lambda _: "/usr/bin/nmap")

    fake_nmap = types.ModuleType("nmap")

    class _Boom:
        def __init__(self):
            raise RuntimeError("nmap crashed")

    fake_nmap.PortScanner = _Boom
    monkeypatch.setitem(sys.modules, "nmap", fake_nmap)
    patch_psutil([fake_conn("127.0.0.1", 8080)])

    scanner = PortScannerModule()
    scanner.scan_mode = "nmap"
    result = await scanner.run()
    assert len(result.items) == 1
    assert result.items[0].detail["port"] == 8080


async def test_nmap_scan_parses_open_ports(clean_db, monkeypatch):
    """TC-NMAP-002: nmap scan thành công -> parse đúng port đang mở."""
    from modules.port_scanner.scanner import PortScannerModule

    monkeypatch.setattr("modules.port_scanner.scanner.shutil.which", lambda _: "/usr/bin/nmap")

    fake_nmap = types.ModuleType("nmap")

    class _Scanner(dict):
        def __init__(self, host_data):
            super().__init__()
            self["scan"] = {"127.0.0.1": host_data}

        def scan(self, hosts, ports, arguments):
            pass

    def _make_scanner():
        return _Scanner({"tcp": {"22": {"state": "open"}, "80": {"state": "closed"}}})

    fake_nmap.PortScanner = _make_scanner
    monkeypatch.setitem(sys.modules, "nmap", fake_nmap)

    scanner = PortScannerModule()
    scanner.scan_mode = "nmap"
    result = await scanner.run()
    assert len(result.items) == 1
    assert result.items[0].detail["port"] == 22


# ------------------------------------------------------- integration (DB)
async def test_diffing_marks_new_and_disappeared(clean_db, patch_psutil):
    from core.executor import execute_scan

    manifest = _manifest()

    patch_psutil([fake_conn("127.0.0.1", 1111)])
    scan1 = await execute_scan(manifest, "scan-1")

    patch_psutil([fake_conn("127.0.0.1", 2222)])
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


async def test_whitelist_overrides_severity(clean_db, patch_psutil):
    from core.executor import execute_scan

    manifest = _manifest()

    patch_psutil([fake_conn("0.0.0.0", 445)])
    scan_id = await execute_scan(manifest, "scan-wl")

    with db.session() as s:
        item = s.scalars(select(ScanItem)).one()
        assert item.severity == "warning"

    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="445:fake.exe", label="server"))
        s.commit()

    patch_psutil([fake_conn("0.0.0.0", 445, pid=7)], {7: FakeProcess("fake.exe")})
    scan_id2 = await execute_scan(manifest, "scan-wl2")

    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == scan_id2)).one()
        assert item2.whitelist_key == "445:fake.exe"
        assert item2.severity == "safe"


# ---------------------------------------------------------------------- utilities


def test_build_summary_correct_counts():
    """UT-SC-001: _build_summary đúng counts."""
    from core.scanner_base import ScanResultItem

    items = [
        ScanResultItem(severity="danger", title="a"),
        ScanResultItem(severity="danger", title="b"),
        ScanResultItem(severity="danger", title="c"),
        ScanResultItem(severity="warning", title="d"),
        ScanResultItem(severity="warning", title="e"),
        ScanResultItem(severity="safe", title="f"),
        ScanResultItem(severity="safe", title="g"),
        ScanResultItem(severity="safe", title="h"),
        ScanResultItem(severity="safe", title="i"),
        ScanResultItem(severity="safe", title="j"),
    ]
    result = _build_summary(items)
    assert result == {"total_open": 10, "danger": 3, "warning": 2, "safe": 5}


def test_build_summary_empty():
    """UT-SC-002: _build_summary list rỗng -> totals 0."""
    result = _build_summary([])
    assert result == {"total_open": 0, "danger": 0, "warning": 0, "safe": 0}


def test_nmap_ports_with_risky_above_1024():
    """UT-SC-003: _nmap_ports với risky ports > 1024."""
    result = _nmap_ports({4444, 8080})
    assert "1-1024" in result
    assert "4444" in result
    assert "8080" in result


def test_nmap_ports_no_risky_above_1024():
    """UT-SC-004: _nmap_ports không có risky > 1024."""
    result = _nmap_ports(set())
    assert result == "1-1024"

    result2 = _nmap_ports({80, 443})
    assert result2 == "1-1024"


def test_build_summary_mix_severities():
    """UT-SC-005: _build_summary items hỗn hợp -> count chính xác."""
    from core.scanner_base import ScanResultItem

    items = [
        ScanResultItem(severity="safe", title="s1"),
        ScanResultItem(severity="warning", title="w1"),
        ScanResultItem(severity="danger", title="d1"),
        ScanResultItem(severity="safe", title="s2"),
    ]
    result = _build_summary(items)
    assert result["total_open"] == 4
    assert result["safe"] == 2
    assert result["warning"] == 1
    assert result["danger"] == 1
