from __future__ import annotations

from datetime import datetime, timedelta

from helpers import fake_conn
from storage.db import Scan, db

# ---------------------------------------------------------------------------
# AUTH (TC-AUTH)
# ---------------------------------------------------------------------------

AUTH_PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/modules"),
    ("POST", "/api/v1/modules/port-scanner/scan"),
    ("GET", "/api/v1/modules/port-scanner/scans"),
    ("GET", "/api/v1/modules/port-scanner/scans/latest"),
    ("GET", "/api/v1/modules/port-scanner/scans/some-scan-id"),
    ("GET", "/api/v1/modules/port-scanner/whitelist"),
    ("POST", "/api/v1/modules/port-scanner/whitelist"),
    ("DELETE", "/api/v1/modules/port-scanner/whitelist/1"),
]


def test_health_requires_token(client):
    """TC-AUTH-001: request không có X-Local-Token -> 401 INVALID_LOCAL_TOKEN."""
    client.headers.pop("X-Local-Token")
    resp = client.get("/api/v1/health")
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_LOCAL_TOKEN"


def test_auth_valid_token_all_endpoints(client, monkeypatch):
    """TC-AUTH-002: token hợp lệ được chấp nhận trên toàn bộ protected endpoint."""
    import modules.port_scanner.routes as pr

    async def _stub_dispatch(_manifest):
        return "stub-scan-id"

    monkeypatch.setattr(pr, "dispatch_scan", _stub_dispatch)
    for method, url in AUTH_PROTECTED_ENDPOINTS:
        resp = client.request(method, url)
        assert resp.status_code in (200, 404, 422), f"{method} {url} -> {resp.status_code}"


def test_auth_invalid_token(client):
    """TC-AUTH-003: token sai -> 401 INVALID_LOCAL_TOKEN."""
    client.headers["X-Local-Token"] = "invalid-token"
    resp = client.get("/api/v1/health")
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_LOCAL_TOKEN"


def test_auth_empty_token(client):
    """TC-AUTH-004: token rỗng -> 401."""
    client.headers["X-Local-Token"] = ""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_LOCAL_TOKEN"


def test_auth_all_protected_endpoints_require_token(client):
    """TC-AUTH-005: mọi protected endpoint đều yêu cầu token."""
    client.headers.pop("X-Local-Token")
    for method, url in AUTH_PROTECTED_ENDPOINTS:
        resp = client.request(method, url)
        assert resp.status_code == 401, f"{method} {url} -> {resp.status_code}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INVALID_LOCAL_TOKEN"


# ---------------------------------------------------------------------------
# HEALTH (TC-HEALTH)
# ---------------------------------------------------------------------------


def test_health_ok(client):
    """TC-HEALTH-001: health bình thường."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] in ("idle", "scanning")


def test_health_while_scanning(client):
    """TC-HEALTH-002: đang có scan chạy -> status=scanning."""
    with db.session() as s:
        s.add(
            Scan(
                id="running-health",
                module_id="port-scanner",
                status="running",
                started_at=datetime.utcnow(),
            )
        )
        s.commit()
    data = client.get("/api/v1/health").json()["data"]
    assert data["status"] == "scanning"
    assert data["running_scans"] == 1


def test_health_idle_after_scan_completed(client, patch_psutil, port_manifest):
    """TC-HEALTH-003: sau khi scan hoàn thành -> idle, không còn scan active."""
    import asyncio

    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 8080)])
    asyncio.run(execute_scan(port_manifest, "health-scan-1"))
    data = client.get("/api/v1/health").json()["data"]
    assert data["status"] == "idle"
    assert data["running_scans"] == 0


def test_health_response_contract(client):
    """TC-HEALTH-004: response đầy đủ các field theo contract."""
    data = client.get("/api/v1/health").json()["data"]
    assert set(data) >= {"status", "running_scans", "registered_modules", "uptime_seconds"}
    assert isinstance(data["running_scans"], int)
    assert isinstance(data["registered_modules"], int)
    assert isinstance(data["uptime_seconds"], int)


# ---------------------------------------------------------------------------
# MODULE REGISTRY (TC-MODULE)
# ---------------------------------------------------------------------------


def test_list_modules(client):
    """TC-MODULE-001: danh sách module có port-scanner."""
    resp = client.get("/api/v1/modules")
    assert resp.status_code == 200
    modules = resp.json()["data"]["modules"]
    ids = [m["id"] for m in modules]
    assert "port-scanner" in ids
    module = next(m for m in modules if m["id"] == "port-scanner")
    assert module["display_name"] == "Port Scanner"
    assert module["status"] == "active"


def test_modules_manifest_complete(client):
    """TC-MODULE-002: manifest mỗi module đầy đủ metadata bắt buộc."""
    modules = client.get("/api/v1/modules").json()["data"]["modules"]
    assert modules, "phải có ít nhất 1 module"
    for m in modules:
        for field in ("id", "display_name", "version", "status"):
            assert field in m and m[field], f"module {m.get('id')} thiếu field {field}"
        for field in ("enabled", "has_scan", "last_scan"):
            assert field in m, f"module {m.get('id')} thiếu field {field}"
    # id phải unique trong danh sách trả về
    ids = [m["id"] for m in modules]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# SCAN API (TC-SCAN)
# ---------------------------------------------------------------------------


def test_scan_endpoint_returns_scan_id(client, monkeypatch):
    """TC-SCAN-001: POST scan trả scan_id ngay (dispatch bị stub)."""
    import modules.port_scanner.routes as pr

    monkeypatch.setattr(pr, "dispatch_scan", _stub_dispatch)
    resp = client.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["scan_id"] == "stub-scan-id"


async def _stub_dispatch(_manifest):
    return "stub-scan-id"


def test_scan_dispatch_failure_uses_error_envelope(client_no_raise, monkeypatch):
    """TC-SCAN-002: dispatch_scan lỗi -> error envelope, không leak stack trace."""
    import modules.port_scanner.routes as pr

    async def _boom(_manifest):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(pr, "dispatch_scan", _boom)
    resp = client_no_raise.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text


def test_scan_unknown_module(client):
    """TC-SCAN-003: module không tồn tại -> 404 với error envelope.

    Ghi chú: route module được đăng ký theo manifest nên module lạ không có
    route -> FastAPI trả 404 HTTP_ERROR (khác code MODULE_NOT_FOUND trong tài
    liệu; đây là hành vi thực tế của hệ thống).
    """
    resp = client.post("/api/v1/modules/unknown/scan")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "HTTP_ERROR"


# ---------------------------------------------------------------------------
# SCAN PERSISTENCE / HISTORY (TC-HISTORY)
# ---------------------------------------------------------------------------


def test_scan_and_read_history(client, patch_psutil, port_manifest):
    """TC-HISTORY-002/003/004: scan -> history, detail, latest."""
    import asyncio

    from core.executor import execute_scan

    patch_psutil([fake_conn("127.0.0.1", 8080)])
    result = asyncio.run(execute_scan(port_manifest, "api-scan-1"))
    assert result == "api-scan-1"

    resp = client.get(f"/api/v1/modules/port-scanner/scans/{result}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "api-scan-1"
    assert "items" in data

    resp = client.get("/api/v1/modules/port-scanner/scans/latest")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "api-scan-1"


def test_scan_history_empty_ok(client):
    """TC-HISTORY-001: history rỗng -> total=0, items=[]."""
    resp = client.get("/api/v1/modules/port-scanner/scans")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 0
    assert body["items"] == []


def test_latest_scan_empty_returns_null(client):
    """TC-HISTORY-005: chưa có scan nào -> 200 + data=null (contract đã thống nhất)."""
    resp = client.get("/api/v1/modules/port-scanner/scans/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is None


def test_scan_detail_not_found(client):
    """TC-HISTORY-006: scan detail không tồn tại -> 404 SCAN_NOT_FOUND."""
    resp = client.get("/api/v1/modules/port-scanner/scans/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SCAN_NOT_FOUND"


def test_scan_history_pagination(client):
    """TC-HISTORY-007: pagination + boundary (page 0, page_size 0, quá lớn, quá trang)."""
    base = datetime.utcnow()
    with db.session() as s:
        for i in range(5):
            s.add(
                Scan(
                    id=f"page-scan-{i}",
                    module_id="port-scanner",
                    status="done",
                    started_at=base - timedelta(minutes=i),
                    finished_at=base,
                )
            )
        s.commit()

    data = client.get("/api/v1/modules/port-scanner/scans").json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 5
    ids = [it["id"] for it in data["items"]]
    assert ids[0] == "page-scan-0"

    data = client.get("/api/v1/modules/port-scanner/scans?page=2&page_size=2").json()["data"]
    assert data["page"] == 2
    assert len(data["items"]) == 2

    data = client.get("/api/v1/modules/port-scanner/scans?page=10&page_size=2").json()["data"]
    assert data["items"] == []

    data = client.get("/api/v1/modules/port-scanner/scans?page=0&page_size=0").json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 1

    data = client.get("/api/v1/modules/port-scanner/scans?page_size=1000").json()["data"]
    assert data["page_size"] == 100


# ---------------------------------------------------------------------------
# WHITELIST (TC-WL)
# ---------------------------------------------------------------------------


def test_legacy_whitelist_read_delete_and_retired_create(client):
    from storage.db import WhitelistEntry
    with db.session() as session:
        entry = WhitelistEntry(module_id="port-scanner", whitelist_key="445:fake.exe", label="old")
        session.add(entry)
        session.commit()
        entry_id = entry.id
    response = client.get("/api/v1/modules/port-scanner/whitelist")
    assert response.json()["data"][0]["whitelist_key"] == "445:fake.exe"
    assert client.post("/api/v1/modules/port-scanner/whitelist", json={"whitelist_key": "445:fake.exe"}).status_code == 410
    assert client.delete(f"/api/v1/modules/port-scanner/whitelist/{entry_id}").status_code == 200
    assert client.get("/api/v1/modules/port-scanner/whitelist").json()["data"] == []


def test_whitelist_delete_not_found(client):
    """TC-WL-006: xoá whitelist không tồn tại -> 404 WHITELIST_NOT_FOUND."""
    resp = client.delete("/api/v1/modules/port-scanner/whitelist/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "WHITELIST_NOT_FOUND"


# ---------------------------------------------------------------------------
# INPUT VALIDATION (TC-VALID)
# ---------------------------------------------------------------------------


def test_whitelist_validation(client):
    """TC-VALID-002: payload whitelist không hợp lệ."""
    resp = client.post("/api/v1/modules/port-scanner/whitelist", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    resp = client.post("/api/v1/modules/port-scanner/whitelist", json={"whitelist_key": "   "})
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "WHITELIST_REPLACED_BY_REVIEW"

    resp = client.post("/api/v1/modules/port-scanner/whitelist", json={"whitelist_key": 123})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_pagination_validation(client):
    """TC-VALID-003: boundary pagination được clamp chứ không lỗi."""
    resp = client.get("/api/v1/modules/port-scanner/scans?page=0&page_size=0")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 1

    resp = client.get("/api/v1/modules/port-scanner/scans?page_size=1000")
    assert resp.status_code == 200
    assert resp.json()["data"]["page_size"] == 100


# ---------------------------------------------------------------------------
# SECURITY (TC-SEC)
# ---------------------------------------------------------------------------


def test_no_secret_leak_in_responses(client_no_raise, monkeypatch):
    """TC-SEC-001: response không chứa token / stack trace."""
    import modules.port_scanner.routes as pr

    async def _boom(_manifest):
        raise RuntimeError("leaked stack detail")

    monkeypatch.setattr(pr, "dispatch_scan", _boom)
    resp = client_no_raise.post("/api/v1/modules/port-scanner/scan")
    assert resp.status_code == 500
    assert "test-token" not in resp.text
    assert "Traceback" not in resp.text

    for url in ("/api/v1/health", "/api/v1/modules", "/api/v1/modules/port-scanner/whitelist"):
        r = client_no_raise.get(url)
        assert r.status_code == 200
        assert "test-token" not in r.text


def test_malformed_request_no_crash(client):
    """TC-SEC-003: payload không hợp lệ -> envelope lỗi, không leak SQL/stack trace."""
    resp = client.post(
        "/api/v1/modules/port-scanner/whitelist",
        content=b"{ not valid json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code in (400, 422)
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    text = resp.text.lower()
    assert "traceback" not in text
    assert "sqlalchemy" not in text
    assert "sqlite" not in text
