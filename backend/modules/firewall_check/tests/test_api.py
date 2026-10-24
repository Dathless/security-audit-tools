import time

import pytest
from sqlalchemy import select

from core.executor import execute_scan
from core.module_registry import discover_modules
from core.scanner_base import ScanError
from storage.db import Scan, ScanDiffLog, ScanItem, db

BASE = "/api/v1/modules/firewall-check"


def test_api_contract_and_isolation(client, mock_firewall):
    assert client.get(f"{BASE}/scans/latest").json() == {"success": True, "data": None, "error": None}
    scan_id = client.post(f"{BASE}/scan").json()["data"]["scan_id"]
    for _ in range(100):
        data = client.get(f"{BASE}/scans/{scan_id}").json()["data"]
        if data["status"] != "running":
            break
        time.sleep(0.01)
    assert data["status"] == "done" and len(data["items"]) == 4
    assert data["summary"]["total_rules"] == 1
    assert data["items"][0]["severity"] == "warning"
    assert client.get(f"{BASE}/scans/latest").json()["data"]["id"] == scan_id
    assert client.get(f"/api/v1/modules/port-scanner/scans/{scan_id}").status_code == 404
    assert client.get(f"{BASE}/scans/missing").status_code == 404
    listing = client.get(f"{BASE}/scans?page=0&page_size=999").json()["data"]
    assert listing["total"] == 1 and listing["page"] == 1 and listing["page_size"] == 100
    assert client.get(f"{BASE}/whitelist").status_code == 404
    assert any(m["id"] == "firewall-check" for m in client.get("/api/v1/modules").json()["data"]["modules"])


@pytest.mark.parametrize("method,path", [("post", "/scan"), ("get", "/scans"), ("get", "/scans/latest"), ("get", "/scans/id")])
def test_all_routes_require_token(client, method, path):
    client.headers.pop("X-Local-Token")
    assert getattr(client, method)(BASE + path).status_code == 401


def test_firewall_websocket_and_replay(client, mock_firewall):
    manifest = discover_modules()["firewall-check"]
    with client.websocket_connect("/ws/scan/firewall-live") as ws:
        client.portal.call(execute_scan, manifest, "firewall-live")
        messages = []
        for _ in range(20):
            message = ws.receive_json()
            messages.append(message)
            if message["type"] in {"done", "error"}:
                break
    assert messages[-1]["type"] == "done"
    assert messages[-1]["summary"]["total_profiles"] == 3
    assert sum(m["type"] == "item_found" for m in messages) == 4
    with client.websocket_connect("/ws/scan/firewall-live") as ws:
        assert ws.receive_json()["replay"] is True


async def test_failure_does_not_replace_diff_baseline(clean_db, mock_firewall, monkeypatch):
    from modules.firewall_check.scanner import FirewallCheckModule
    manifest = discover_modules()["firewall-check"]
    await execute_scan(manifest, "fw-first")
    original = FirewallCheckModule._collect
    def denied():
        raise ScanError("SCAN_PERMISSION_DENIED", "permission denied")
    monkeypatch.setattr(FirewallCheckModule, "_collect", staticmethod(denied))
    await execute_scan(manifest, "fw-error")
    monkeypatch.setattr(FirewallCheckModule, "_collect", staticmethod(original))
    await execute_scan(manifest, "fw-retry")
    with db.session() as session:
        assert session.get(Scan, "fw-error").status == "error"
        assert not any(i.is_new for i in session.scalars(select(ScanItem).where(ScanItem.scan_id == "fw-retry")))
    mock_firewall["rules"] = []
    await execute_scan(manifest, "fw-gone")
    with db.session() as session:
        gone = session.scalars(select(ScanDiffLog).where(ScanDiffLog.scan_id == "fw-gone", ScanDiffLog.change_type == "disappeared")).all()
        assert [r.whitelist_key for r in gone] == ["rule:rule-1"]


def test_openapi_documents_module(client):
    paths = client.get("/openapi.json").json()["paths"]
    for suffix in ("/scan", "/scans", "/scans/latest", "/scans/{scan_id}"):
        assert BASE + suffix in paths
