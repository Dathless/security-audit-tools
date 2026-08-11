from __future__ import annotations

import socket


class FakeConn:
    def __init__(self, ip, port, pid=None):
        self.laddr = (ip, port)
        self.type = socket.SOCK_STREAM
        self.status = "LISTEN"
        self.pid = pid


class FakePsutil:
    CONN_LISTEN = "LISTEN"
    AccessDenied = PermissionError
    NoSuchProcess = ProcessLookupError
    ZombieProcess = ProcessLookupError

    def __init__(self, conns):
        self.connections = conns

    def net_connections(self, kind="inet"):
        return self.connections

    def Process(self, pid):
        raise self.NoSuchProcess(pid)


def fake_conn(ip, port, pid=None):
    return FakeConn(ip, port, pid)


def test_health_requires_token(client):
    client.headers.pop("X-Local-Token")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_LOCAL_TOKEN"


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] in ("idle", "scanning")


def test_list_modules(client):
    resp = client.get("/api/v1/modules")
    assert resp.status_code == 200
    modules = resp.json()["data"]["modules"]
    ids = [m["id"] for m in modules]
    assert "port-scanner" in ids
    module = next(m for m in modules if m["id"] == "port-scanner")
    assert module["display_name"] == "Port Scanner"
    assert module["status"] == "active"


def test_scan_and_read_history(client, monkeypatch):
    from core.executor import execute_scan
    from core.module_registry import discover_modules

    import asyncio
    import modules.port_scanner.scanner as ms

    ms.psutil = FakePsutil([fake_conn("127.0.0.1", 8080)])

    manifest = discover_modules()["port-scanner"]

    def _sync_dispatch(_manifest):
        return asyncio.run(execute_scan(_manifest, "api-scan-1"))

    result = _sync_dispatch(manifest)
    assert result == "api-scan-1"

    resp = client.get(f"/api/v1/modules/port-scanner/scans/{result}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "api-scan-1"
    assert "items" in data

    # latest trả về đúng lượt gần nhất
    resp = client.get("/api/v1/modules/port-scanner/scans/latest")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "api-scan-1"


def test_scan_endpoint_returns_scan_id(client, monkeypatch):
    import modules.port_scanner.routes as pr

    monkeypatch.setattr(pr, "dispatch_scan", _stub_dispatch)
    resp = client.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["scan_id"] == "stub-scan-id"


async def _stub_dispatch(_manifest):
    return "stub-scan-id"


def test_scan_history_empty_ok(client):
    resp = client.get("/api/v1/modules/port-scanner/scans")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 0
    assert body["items"] == []


def test_whitelist_crud(client):
    resp = client.get("/api/v1/modules/port-scanner/whitelist")
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    resp = client.post(
        "/api/v1/modules/port-scanner/whitelist",
        json={"whitelist_key": "445:fake.exe", "label": "server chia sẻ"},
    )
    assert resp.status_code == 200
    entry_id = resp.json()["data"]["id"]

    resp = client.get("/api/v1/modules/port-scanner/whitelist")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["whitelist_key"] == "445:fake.exe"

    # trùng key → không thêm mới
    resp = client.post(
        "/api/v1/modules/port-scanner/whitelist", json={"whitelist_key": "445:fake.exe"}
    )
    assert resp.json()["data"]["created"] is False

    resp = client.delete(f"/api/v1/modules/port-scanner/whitelist/{entry_id}")
    assert resp.status_code == 200

    resp = client.get("/api/v1/modules/port-scanner/whitelist")
    assert resp.json()["data"] == []


def test_whitelist_delete_not_found(client):
    resp = client.delete("/api/v1/modules/port-scanner/whitelist/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "WHITELIST_NOT_FOUND"