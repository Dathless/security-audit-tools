from __future__ import annotations

import pytest

from core.config import ModuleSettings
from core.scanner_base import ScanError
from helpers import FakeProcess, fake_conn
from modules.port_scanner.scanner import PortScannerModule


async def test_endpoint_identity_separates_protocol_family_and_bind(clean_db, patch_psutil):
    patch_psutil([
        fake_conn("127.0.0.1", 8080, 1), fake_conn("0.0.0.0", 8080, 1),
        fake_conn("127.0.0.1", 8080, 1, udp=True), fake_conn("::1", 8080, 1),
        fake_conn("fe80::1%3", 8080, 1), fake_conn("fe80::1%4", 8080, 1),
    ], {1: FakeProcess("app.exe")})
    scanner = PortScannerModule()
    result = await scanner.run()
    assert len({scanner.get_whitelist_key(item) for item in result.items}) == 6
    assert result.summary["unique_ports"] == 1
    assert result.summary["total_endpoints"] == 6


async def test_same_endpoint_retains_multiple_owners(clean_db, patch_psutil):
    patch_psutil([fake_conn("127.0.0.1", 8080, 1), fake_conn("127.0.0.1", 8080, 2)],
                 {1: FakeProcess("first.exe"), 2: FakeProcess("second.exe")})
    result = await PortScannerModule().run()
    assert len(result.items) == 1
    assert {owner["name"] for owner in result.items[0].detail["owners"]} == {"first.exe", "second.exe"}


async def test_inventory_denial_is_error_not_fake_endpoint(clean_db, patch_psutil):
    patch_psutil([], deny_net=True)
    with pytest.raises(ScanError) as error:
        await PortScannerModule().run()
    assert error.value.code == "SCAN_PERMISSION_DENIED"


@pytest.mark.parametrize("address,port,severity", [
    ("127.0.0.1", 8080, "safe"), ("::1", 8080, "safe"),
    ("127.0.0.1", 4444, "warning"), ("0.0.0.0", 8080, "warning"),
    ("192.168.1.2", 8080, "warning"), ("0.0.0.0", 4444, "danger"),
    ("::", 4444, "danger"), ("::", 8080, "warning"), ("::1", 4444, "warning"),
    ("::ffff:127.0.0.1", 8080, "safe"), ("fe80::1%3", 8080, "warning"),
])
async def test_evidence_risk_matrix(clean_db, patch_psutil, address, port, severity):
    patch_psutil([fake_conn(address, port, 1)], {1: FakeProcess("app.exe")})
    result = await PortScannerModule().run()
    assert result.items[0].severity == severity


async def test_all_risk_reasons_survive_and_metadata_denial_is_explicit(clean_db, patch_psutil):
    patch_psutil([fake_conn("0.0.0.0", 4444, 1)], {1: FakeProcess(access_denied=True)})
    result = await PortScannerModule().run()
    item = result.items[0]
    assert set(item.detail["reasons"]) == {
        "PORT_IN_RISKY_LIST", "LISTENING_ON_ALL_INTERFACES", "PROCESS_IDENTITY_UNKNOWN",
    }
    assert item.detail["owners"][0]["status"]["exe"] == "access_denied"
    assert result.partial_result is False
    assert result.summary["metadata_incomplete_count"] == 1


async def test_thousand_sockets_read_inventory_once_and_metadata_per_pid(clean_db, patch_psutil):
    fake = patch_psutil([fake_conn("127.0.0.1", 10000 + i, i % 50 + 1) for i in range(1000)],
                        {i: FakeProcess(f"app{i}.exe") for i in range(1, 51)})
    updates = []
    async def progress(current, total, message):
        updates.append((current, total))
    result = await PortScannerModule().run(progress)
    assert len(result.items) == 1000
    assert result.summary["unique_processes"] == 50
    assert fake.inventory_calls == 1
    assert fake.process_calls == 50
    assert updates[-1] == (1000, 1000)
    assert len(updates) <= 22


def test_empty_risky_port_configuration_is_honored(monkeypatch):
    monkeypatch.setattr("modules.port_scanner.scanner.config.module",
                        lambda _: ModuleSettings(extra={"known_risky_ports": []}))
    assert PortScannerModule().known_risky_ports == set()


@pytest.mark.parametrize("ports", [[0], [65536], [-1], [True], ["invalid"]])
def test_invalid_port_configuration_is_structured_error(monkeypatch, ports):
    monkeypatch.setattr("modules.port_scanner.scanner.config.module",
                        lambda _: ModuleSettings(extra={"known_risky_ports": ports}))
    with pytest.raises(ScanError) as error:
        PortScannerModule()
    assert error.value.code == "SCAN_CONFIG_INVALID"
