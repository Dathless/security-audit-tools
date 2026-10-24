from __future__ import annotations

from helpers import fake_conn
from storage.db import db


def test_progress_events_reach_ws_client(client, patch_psutil, port_manifest):
    """CL-RT-001: execute_scan chạy -> WS client nhận progress events."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([fake_conn("127.0.0.1", 8080)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    types = [m["type"] for m in messages]
    assert "progress" in types


def test_item_found_events_reach_ws_client(client, patch_psutil, port_manifest):
    """CL-RT-002: Scanner tìm thấy port -> WS client nhận item_found."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([fake_conn("127.0.0.1", 4444)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    items = [m for m in messages if m["type"] == "item_found"]
    assert len(items) >= 1
    assert items[0]["item"]["severity"] in ("safe", "warning", "danger")
    assert items[0]["item"]["title"]


def test_done_event_reaches_ws_client(client, patch_psutil, port_manifest):
    """CL-RT-003: Scan xong -> WS client nhận done."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([fake_conn("127.0.0.1", 80)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    assert messages[-1]["type"] == "done"
    assert messages[-1]["scan_id"] == scan_id


def test_error_event_reaches_ws_client(client, patch_psutil, port_manifest, monkeypatch):
    """CL-RT-004: Scanner fail -> WS client nhận error."""
    from core.scanner_base import ScanError
    from modules.port_scanner.scanner import PortScannerModule
    from storage.db import Scan
    from datetime import datetime
    import uuid

    async def _boom(self, progress_cb=None):
        raise ScanError("SCAN_ERR", "test error")

    monkeypatch.setattr(PortScannerModule, "run", _boom)

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([])
        from core.executor import execute_scan
        client.portal.call(execute_scan, port_manifest, scan_id)
        m = ws.receive_json()

    assert m["type"] == "error"
    assert m["code"] == "SCAN_ERR"


def test_event_order_progress_item_done(client, patch_psutil, port_manifest):
    """CL-RT-005: Thứ tự events: progress -> item -> done."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([fake_conn("127.0.0.1", 4444)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    types = [m["type"] for m in messages]
    assert types[-1] == "done"
    first_progress = next(i for i, t in enumerate(types) if t == "progress")
    first_item = next(i for i, t in enumerate(types) if t == "item_found")
    assert first_progress < first_item


def test_late_client_receives_replay(client, patch_psutil, port_manifest):
    """CL-RT-006: Scan done rồi -> client connect WS -> nhận done event với replay:true."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    patch_psutil([fake_conn("127.0.0.1", 80)])
    from core.executor import execute_scan
    client.portal.call(execute_scan, port_manifest, scan_id)

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        m = ws.receive_json()

    assert m["type"] == "done"
    assert m["replay"] is True
    assert m["scan_id"] == scan_id


def test_two_clients_both_receive_events(client, patch_psutil, port_manifest):
    """CL-RT-007: 2 WS connections cùng scan -> cả 2 nhận cùng events."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws_a:
        with client.websocket_connect(f"/ws/scan/{scan_id}") as ws_b:
            patch_psutil([fake_conn("127.0.0.1", 80)])
            client.portal.call(execute_scan, port_manifest, scan_id)
            msgs_a = []
            for _ in range(50):
                m = ws_a.receive_json()
                msgs_a.append(m)
                if m["type"] == "done":
                    break
            msgs_b = []
            for _ in range(50):
                m = ws_b.receive_json()
                msgs_b.append(m)
                if m["type"] == "done":
                    break

    assert msgs_a[-1]["type"] == "done"
    assert msgs_b[-1]["type"] == "done"
    assert msgs_a[-1]["scan_id"] == msgs_b[-1]["scan_id"]


def test_global_channel_receives_done(client, patch_psutil, port_manifest):
    """CL-RT-008: /ws/events -> nhận done từ scan bất kỳ."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect("/ws/events") as ws:
        patch_psutil([fake_conn("127.0.0.1", 80)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    assert messages[-1]["type"] == "done"
    assert messages[-1]["scan_id"] == scan_id


def test_progress_message_format(client, patch_psutil, port_manifest):
    """CL-RT-009: Assert progress event có current, total, message."""
    from core.executor import execute_scan
    from storage.db import Scan
    from datetime import datetime
    import uuid

    scan_id = uuid.uuid4().hex
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status="running", started_at=datetime.utcnow()))
        s.commit()

    with client.websocket_connect(f"/ws/scan/{scan_id}") as ws:
        patch_psutil([fake_conn("127.0.0.1", 80)])
        client.portal.call(execute_scan, port_manifest, scan_id)
        messages = []
        for _ in range(50):
            m = ws.receive_json()
            messages.append(m)
            if m["type"] == "done":
                break

    progress_msgs = [m for m in messages if m["type"] == "progress"]
    assert len(progress_msgs) >= 1
    for pm in progress_msgs:
        assert "current" in pm
        assert "total" in pm
        assert "message" in pm
