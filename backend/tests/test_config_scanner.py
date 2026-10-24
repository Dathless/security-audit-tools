from __future__ import annotations

from core.config import ModuleSettings


def test_custom_risky_ports_from_config(clean_db):
    from modules.port_scanner.scanner import PortScannerModule
    scanner = PortScannerModule()
    scanner.known_risky_ports = {22, 8080}
    entry = {"ip": "127.0.0.1", "owners": [{"exe": "C:\\Apps\\app.exe", "username": "TEST"}]}
    for port in (22, 8080):
        assert scanner._classify({**entry, "port": port}) == ("warning", ["PORT_IN_RISKY_LIST"])
    assert scanner._classify({**entry, "port": 4444}) == ("safe", [])


def test_default_risky_ports():
    """CL-CS-002: Config không có known_risky_ports -> dùng default [4444, 1337, 31337]."""
    from modules.port_scanner.scanner import PortScannerModule

    scanner = PortScannerModule()
    assert 4444 in scanner.known_risky_ports
    assert 1337 in scanner.known_risky_ports
    assert 31337 in scanner.known_risky_ports


def test_socket_mode_default():
    """CL-CS-003: Config scan_mode: socket -> scanner dùng _scan_socket."""
    from modules.port_scanner.scanner import PortScannerModule

    scanner = PortScannerModule()
    assert scanner.scan_mode == "socket"


def test_module_settings_custom_risky_ports():
    """CL-CS-extra: ModuleSettings.get trả custom risky ports từ config."""
    m = ModuleSettings.from_config({"known_risky_ports": [22, 80]})
    assert m.get("known_risky_ports") == [22, 80]


async def test_legacy_nmap_config_uses_socket(clean_db, patch_psutil, monkeypatch, caplog):
    from helpers import fake_conn
    from core.config import config
    from modules.port_scanner.models import PortScannerConfig
    from modules.port_scanner.scanner import PortScannerModule
    from storage.db import db

    monkeypatch.setattr(config, "module", lambda _: ModuleSettings.from_config({"scan_mode": "nmap"}))
    patch_psutil([fake_conn("::1", 8080)])
    scanner = PortScannerModule()
    assert scanner.scan_mode == "socket"
    result = await scanner.run()
    assert result.items[0].detail["listener"] == "::1"
    assert "nmap" in caplog.text.lower()
    with db.session() as session:
        assert session.get(PortScannerConfig, "port-scanner").scan_mode == "socket"
