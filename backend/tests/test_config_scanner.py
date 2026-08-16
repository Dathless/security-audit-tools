from __future__ import annotations

from core.config import ModuleSettings


def test_custom_risky_ports_from_config(clean_db, monkeypatch):
    """CL-CS-001: Config known_risky_ports: [22, 8080] -> scanner classify 22 = danger, 4444 = safe."""
    from helpers import fake_conn
    from modules.port_scanner.scanner import PortScannerModule

    async def _run():
        pass

    scanner = PortScannerModule()
    scanner.known_risky_ports = {22, 8080}

    assert scanner._classify({"port": 22, "ip": "127.0.0.1", "pid": None, "process_name": "", "protocol": "tcp", "permission_denied": False}) == ("danger", ["PORT_IN_RISKY_LIST"])
    assert scanner._classify({"port": 8080, "ip": "127.0.0.1", "pid": None, "process_name": "", "protocol": "tcp", "permission_denied": False}) == ("danger", ["PORT_IN_RISKY_LIST"])
    assert scanner._classify({"port": 4444, "ip": "127.0.0.1", "pid": None, "process_name": "", "protocol": "tcp", "permission_denied": False}) == ("safe", [])


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
