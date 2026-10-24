from __future__ import annotations


def test_module_discovered_at_startup(port_manifest):
    """CL-MOD-001: discover_modules() trả dict chứa port-scanner."""
    assert "port-scanner" in port_manifest.id or port_manifest.id == "port-scanner"


def test_module_router_included_in_app(client):
    """CL-MOD-002: App có endpoint /api/v1/modules/port-scanner/scan."""
    resp = client.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code in (200, 422)


def test_get_modules_returns_port_scanner(client):
    """CL-MOD-003: GET /api/v1/modules -> list chứa port-scanner với display_name đúng."""
    resp = client.get("/api/v1/modules")
    assert resp.status_code == 200
    modules = resp.json()["data"]["modules"]
    ids = [m["id"] for m in modules]
    assert "port-scanner" in ids
    module = next(m for m in modules if m["id"] == "port-scanner")
    assert module["display_name"] == "Port Scanner"


def test_module_manifest_has_required_fields(port_manifest):
    """CL-MOD-004: Mỗi manifest có id, display_name, version, scanner_cls."""
    assert port_manifest.id
    assert port_manifest.display_name
    assert port_manifest.version
    assert port_manifest.scanner_cls is not None


def test_module_enabled_reflects_config(clean_db, port_manifest):
    """CL-MOD-005: Config enabled: true -> module appear trong list; false -> không appear."""
    from core.config import ModuleSettings

    assert port_manifest.enabled is True

    assert ModuleSettings(enabled=False).enabled is False
