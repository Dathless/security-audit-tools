from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict], Awaitable[None]]


@dataclass
class _Subscription:
    handler: Handler
    pattern: str


class EventBus:
    """Pub/sub nội bộ để tách module khỏi WebSocket/API.

    Topic theo pattern:  scan.<scan_id>.progress
                          scan.<scan_id>.item
                          scan.<scan_id>.done
                          scan.<scan_id>.error
    Handler nhận (topic, message). Gửi tuần tự trong cùng event loop để
    đảm bảo thứ tự message tới đúng client.
    """

    def __init__(self) -> None:
        self._subs: list[_Subscription] = []

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        subs = _Subscription(handler=handler, pattern=pattern)
        self._subs.append(subs)

        def unsubscribe() -> None:
            if subs in self._subs:
                self._subs.remove(subs)

        return unsubscribe

    async def publish(self, topic: str, message: dict) -> None:
        for subs in list(self._subs):
            if _match(subs.pattern, topic):
                try:
                    await subs.handler(topic, message)
                except Exception:
                    logger.exception("Event handler lỗi với topic=%s", topic)


def _match(pattern: str, topic: str) -> bool:
    """Wildcard đơn giản: '*' khớp 1 segment, '#' khớp mọi segment còn lại."""
    p_parts = pattern.split(".")
    t_parts = topic.split(".")
    for i, part in enumerate(p_parts):
        if part == "#":
            return True
        if i >= len(t_parts):
            return False
        if part != "*" and part != t_parts[i]:
            return False
    return len(p_parts) == len(t_parts)


event_bus = EventBus()