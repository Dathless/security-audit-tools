from __future__ import annotations

import json
import logging
from typing import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()

GLOBAL_PATTERNS = [
    "scan.*.progress",
    "scan.*.item",
    "scan.*.done",
    "scan.*.error",
]


class _Channel:
    """1 kênh WS: map connection key → set(WebSocket), subscribe vào event_bus."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._unsubs: dict[str, list[Callable[[], None]]] = {}

    async def connect(self, websocket: WebSocket, key: str, patterns: list[str]) -> None:
        await websocket.accept()
        self._connections.setdefault(key, set()).add(websocket)
        unsubs = self._unsubs.setdefault(key, [])
        for pattern in patterns:
            unsubs.append(event_bus.subscribe(pattern, self._make_send(key, websocket)))

    def _make_send(self, key: str, websocket: WebSocket):
        async def _send(topic: str, message: dict) -> None:
            await self._send_to(key, websocket, message)

        return _send

    async def _send_to(self, key: str, websocket: WebSocket, message: dict) -> None:
        if websocket not in self._connections.get(key, set()):
            return
        if websocket.application_state != WebSocketState.CONNECTED:
            return
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            logger.debug("Gửi WS thất bại (client đóng), key=%s", key)

    async def disconnect(self, websocket: WebSocket, key: str) -> None:
        conns = self._connections.get(key)
        if conns:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(key, None)
                for unsub in self._unsubs.pop(key, []):
                    unsub()
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


scan_channel = _Channel()
global_channel = _Channel()


def _scan_patterns(scan_id: str) -> list[str]:
    return [
        f"scan.{scan_id}.progress",
        f"scan.{scan_id}.item",
        f"scan.{scan_id}.done",
        f"scan.{scan_id}.error",
    ]


@router.websocket("/ws/scan/{scan_id}")
async def ws_scan(websocket: WebSocket, scan_id: str) -> None:
    await scan_channel.connect(websocket, scan_id, _scan_patterns(scan_id))
    await _replay_scan_state(websocket, scan_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await scan_channel.disconnect(websocket, scan_id)


async def _replay_scan_state(websocket: WebSocket, scan_id: str) -> None:
    """Nếu client subscribe muộn (scan đã xong/lỗi), gửi lại trạng thái cuối."""
    import json as _json

    from storage.db import Scan, db

    with db.session() as s:
        row = s.get(Scan, scan_id)
        if row is None:
            return
        if row.status == "done":
            message = {
                "type": "done",
                "scan_id": scan_id,
                "summary": _json.loads(row.summary_json) if row.summary_json else {},
                "partial_result": bool(row.partial_result),
                "replay": True,
            }
        elif row.status == "error":
            message = {
                "type": "error",
                "code": "SCAN_FAILED",
                "message": row.error_message or "Quét thất bại.",
            }
        else:
            return
    try:
        await websocket.send_text(json.dumps(message, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Kênh global — mọi client đang mở nhận được scan của scheduler (mục 5.2)."""
    key = "global"
    await global_channel.connect(websocket, key, GLOBAL_PATTERNS)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await global_channel.disconnect(websocket, key)