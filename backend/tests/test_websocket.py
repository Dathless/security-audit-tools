from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from starlette.websockets import WebSocketDisconnect

from helpers import fake_conn
from storage.db import Scan, db


@pytest.mark.parametrize("path", ["/ws/events", "/ws/scan/ghost-scan"])
@pytest.mark.parametrize("token,origin", [(None, None), ("wrong", None), ("test-token", "https://untrusted.example")])
def test_websocket_rejects_unauthorized_clients(client, path, token, origin):
    client.headers.pop("X-Local-Token", None)
    headers = {}
    if token:
        headers["X-Local-Token"] = token
    if origin:
        headers["Origin"] = origin
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path, headers=headers):
            pass
    assert exc.value.code == 1008


def test_browser_can_authenticate_without_token_in_url(client):
    client.headers.pop("X-Local-Token", None)
    with client.websocket_connect("/ws/scan/ghost-scan", subprotocols=["sec-audit", "token.test-token"], headers={"Origin": "http://127.0.0.1:5173"}) as ws:
        assert ws.accepted_subprotocol == "sec-audit"


def test_replay_failed_scan_preserves_error_message(client):
    with db.session() as session:
        session.add(Scan(id="failed-replay", module_id="firewall-check", status="error", started_at=datetime.utcnow(), error_message="Cannot read Windows Firewall"))
        session.commit()
    with client.websocket_connect("/ws/scan/failed-replay") as ws:
        message = ws.receive_json()
        assert message == {"type": "error", "code": "SCAN_FAILED", "message": "Cannot read Windows Firewall"}


def _make_running_scan(scan_id=None) -> str:
    scan_id = scan_id or uuid.uuid4().hex
    with db.session() as s:
        s.add(
            Scan(
                id=scan_id,
                module_id="port-scanner",
                status="running",
                started_at=datetime.utcnow(),
            )
        )
        s.commit()
    return scan_id


def _run_scan_via_portal(client, manifest, scan_id, patch_psutil, conns):
    """Chạy execute_scan trên event loop của TestClient để WS nhận event."""
    from core.executor import execute_scan

    patch_psutil(conns)
    client.portal.call(execute_scan, manifest, scan_id)


def _receive_until_done(ws, max_messages=50) -> list[dict]:
    messages = []
    for _ in range(max_messages):
        m = ws.receive_json()
        messages.append(m)
        if m["type"] == "done":
            break
    else:
        raise AssertionError("không nhận được event done qua WebSocket")
    return messages


def test_ws_connect_valid_scan(client):
    """TC-WS-001: connect /ws/scan/{scan_id} với scan hợp lệ -> accept thành công."""
    scan_id = _make_running_scan()
    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        pass


def test_ws_invalid_scan_id_connection_accepted(client):
    """TC-WS-002: scan_id không tồn tại -> connection vẫn accept, không lỗi, không replay."""
    with client.websocket_connect("/ws/scan/ghost-scan") as ws:
        pass


def test_ws_progress_item_done_events(client, patch_psutil, port_manifest):
    """TC-WS-003/004/005/007: progress -> item_found -> done với schema đúng."""
    scan_id = _make_running_scan()
    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        _run_scan_via_portal(
            client,
            port_manifest,
            scan_id,
            patch_psutil,
            [fake_conn("127.0.0.1", 4444), fake_conn("127.0.0.1", 8080)],
        )
        messages = _receive_until_done(ws)

    types = [m["type"] for m in messages]
    assert types[-1] == "done"
    assert types.count("item_found") == 2
    assert "progress" in types

    # TC-WS-007: không được phép done trước item_found
    assert types.index("done") > max(i for i, t in enumerate(types) if t == "item_found")

    for m in messages:
        if m["type"] == "progress":
            assert "current" in m and "total" in m
            assert 0 <= m["current"] <= m["total"]
        elif m["type"] == "item_found":
            item = m["item"]
            assert item["severity"] in ("safe", "warning", "danger")
            assert item["title"]
            assert item["detail"]
        elif m["type"] == "done":
            assert m["scan_id"] == scan_id
            assert "summary" in m
            assert "partial_result" in m


def test_ws_error_event(client, patch_psutil, port_manifest, monkeypatch):
    """TC-WS-006: scanner failure -> error event với code ổn định."""
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule

    async def _boom(self, progress_cb=None):
        raise ScanError("SCAN_PERMISSION_DENIED", "cannot read connections")

    monkeypatch.setattr(PortScannerModule, "run", _boom)
    scan_id = _make_running_scan()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        _run_scan_via_portal(client, port_manifest, scan_id, patch_psutil, [])
        m = ws.receive_json()

    assert m["type"] == "error"
    assert m["code"] == "SCAN_PERMISSION_DENIED"


def test_ws_replay_after_done(client, patch_psutil, port_manifest):
    """TC-WS-008: connect muộn sau khi scan xong -> nhận done + replay=true."""
    scan_id = _make_running_scan()
    _run_scan_via_portal(client, port_manifest, scan_id, patch_psutil, [fake_conn("127.0.0.1", 8080)])

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        m = ws.receive_json()

    assert m["type"] == "done"
    assert m["scan_id"] == scan_id
    assert m["replay"] is True


def test_ws_multiple_subscribers(client, patch_psutil, port_manifest):
    """TC-WS-009: hai client cùng subscribe một scan -> cả hai nhận event."""
    scan_id = _make_running_scan()
    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws_a:
        with client.websocket_connect(f"/ws/scan/{scan_id}") as ws_b:
            _run_scan_via_portal(
                client,
                port_manifest,
                scan_id,
                patch_psutil,
                [fake_conn("127.0.0.1", 8080)],
            )
            a_done = _receive_until_done(ws_a)
            b_done = _receive_until_done(ws_b)

    assert a_done[-1]["type"] == "done"
    assert b_done[-1]["type"] == "done"
    assert a_done[-1]["scan_id"] == scan_id
    assert b_done[-1]["scan_id"] == scan_id


def test_ws_global_events_channel(client, patch_psutil, port_manifest):
    """Kênh global /ws/events nhận event done của scan bất kỳ."""
    scan_id = _make_running_scan()
    with client.websocket_connect("/ws/events") as ws:
        _run_scan_via_portal(client, port_manifest, scan_id, patch_psutil, [fake_conn("127.0.0.1", 8080)])
        messages = _receive_until_done(ws)

    assert messages[-1]["type"] == "done"
    assert messages[-1]["scan_id"] == scan_id
