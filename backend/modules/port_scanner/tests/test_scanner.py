from __future__ import annotations


import pytest
from sqlalchemy import select

from helpers import FakeProcess, fake_conn
from modules.port_scanner.scanner import PortScannerModule, _build_summary
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


async def test_socket_inventory_keeps_udp_ipv6_and_excludes_connected_tcp(clean_db, patch_psutil, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "nmap", None)
    udp = fake_conn("::", 5353, udp=True)
    connected = fake_conn("127.0.0.1", 50000)
    connected.status = "ESTABLISHED"
    unbound = fake_conn("127.0.0.1", 0)
    unbound.laddr = None
    patch_psutil([udp, connected, unbound, fake_conn("::1", 8080)])
    result = await PortScannerModule().run()
    assert {(i.detail["port"], i.detail["protocol"]) for i in result.items} == {(5353, "udp"), (8080, "tcp")}


async def test_run_classify_severities(clean_db, patch_psutil):
    from modules.port_scanner.scanner import PortScannerModule

    conns = [
        fake_conn("127.0.0.1", 8080, 1),
        fake_conn("0.0.0.0", 445, 1),
        fake_conn("127.0.0.1", 4444, 1),
    ]
    patch_psutil(conns, {1: FakeProcess("app.exe")})

    result = await PortScannerModule().run()
    by_port = {item.detail["port"]: item.severity for item in result.items}
    assert by_port[4444] == "warning"
    assert by_port[445] == "warning"
    assert by_port[8080] == "safe"
    assert {key: result.summary[key] for key in ("total_open", "danger", "warning", "safe")} == {"total_open": 3, "danger": 0, "warning": 2, "safe": 1}

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
    assert result.partial_result is False
    item = next(i for i in result.items if i.detail["port"] == 9000)
    assert item.detail["permission_denied"] is True


# ------------------------------------------------------------- severity matrix
@pytest.mark.parametrize(
    "ip,port,pid,proc,expected",
    [
        ("127.0.0.1", 8080, None, None, "warning"),  # TC-SCANNER-003 localhost safe
        ("127.0.0.1", 443, None, None, "warning"),
        ("0.0.0.0", 8080, None, None, "warning"),  # TC-SCANNER-004 wildcard bind
        ("::", 8080, None, None, "warning"),
        ("127.0.0.1", 4444, None, None, "warning"),  # TC-SCANNER-005 risky port
        ("127.0.0.1", 1337, None, None, "warning"),
        ("127.0.0.1", 31337, None, None, "warning"),
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
    assert item.severity == "warning"
    assert item.detail["owners"][0]["status"]["exe"] == "gone"


@pytest.mark.parametrize("port,process", [(22, "nginx.exe"), (80, "nginx.exe"), (443, "httpd.exe"), (5432, "postgres.exe")])
async def test_process_name_does_not_prove_service_mismatch(clean_db, patch_psutil, port, process):
    """A process can legitimately listen on any port; its name is not protocol evidence."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", port, pid=10)], {10: FakeProcess(process)})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.severity == "safe"
    assert item.detail["reasons"] == []


@pytest.mark.parametrize("ip,port,note", [
    ("127.0.0.1", 8080, "Không phát hiện theo tiêu chí hiện tại"),
    ("0.0.0.0", 8080, "Bind trên mọi giao diện; chưa xác minh khả năng truy cập từ mạng"),
    ("127.0.0.1", 4444, "Cổng nằm trong danh sách cần chú ý; không phải bằng chứng malware"),
])
async def test_scan_preserves_legacy_detail_fields(clean_db, patch_psutil, ip, port, note):
    patch_psutil([fake_conn(ip, port, 7)], {7: FakeProcess("app.exe")})
    item = (await PortScannerModule().run()).items[0]
    assert item.detail["ip"] == item.detail["listener"] == ip
    assert item.detail["note"] == note


async def test_ssh_process_on_loopback_has_no_finding(clean_db, patch_psutil):
    """A named process on a non-risky loopback port has no finding."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", 22, pid=10)], {10: FakeProcess("sshd.exe")})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.detail["reasons"] == []


async def test_risky_port_takes_priority_over_process_name(clean_db, patch_psutil):
    """A familiar executable name does not override the risky port policy."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", 4444, pid=10)], {10: FakeProcess("nginx.exe")})

    result = await PortScannerModule().run()
    assert len(result.items) == 1
    item = result.items[0]
    assert item.severity == "warning"
    assert "PORT_IN_RISKY_LIST" in item.detail["reasons"]
    assert item.detail["reasons"] == ["PORT_IN_RISKY_LIST"]


async def test_whitelist_key_with_process_name(clean_db, patch_psutil):
    """get_whitelist_key: có process name -> 'port:process'."""
    from modules.port_scanner.scanner import PortScannerModule

    patch_psutil([fake_conn("127.0.0.1", 445, pid=7)], {7: FakeProcess("fake.exe")})

    result = await PortScannerModule().run()
    item = result.items[0]
    key = PortScannerModule().get_whitelist_key(item)
    assert key == '["endpoint-v2","tcp","ipv4","127.0.0.1",445]'


async def test_net_connections_access_denied_is_structured_error(clean_db, patch_psutil):
    from core.scanner_base import ScanError
    patch_psutil([], deny_net=True)
    with pytest.raises(ScanError) as error:
        await PortScannerModule().run()
    assert error.value.code == "SCAN_PERMISSION_DENIED"


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
        assert scan1_items[0].is_new is False
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


async def test_legacy_whitelist_does_not_override_risk(clean_db, patch_psutil):
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
        assert item2.whitelist_key == '["endpoint-v2","tcp","ipv4","0.0.0.0",445]'
        assert item2.severity == "warning"


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
    assert {key: result[key] for key in ("total_open", "danger", "warning", "safe")} == {"total_open": 10, "danger": 3, "warning": 2, "safe": 5}


def test_build_summary_empty():
    """UT-SC-002: _build_summary list rỗng -> totals 0."""
    result = _build_summary([])
    assert {key: result[key] for key in ("total_open", "danger", "warning", "safe")} == {"total_open": 0, "danger": 0, "warning": 0, "safe": 0}


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
