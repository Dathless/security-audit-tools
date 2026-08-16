from __future__ import annotations

from core.event_bus import EventBus, _match


def _recorder():
    calls: list = []

    async def handler(topic, message):
        calls.append((topic, message))

    return calls, handler


async def test_publish_subscribe():
    """TC-EVENT-001: subscribe(topic) -> publish(topic) -> callback nhận event."""
    bus = EventBus()
    calls, handler = _recorder()
    bus.subscribe("scan.abc.progress", handler)
    await bus.publish("scan.abc.progress", {"type": "progress"})
    assert len(calls) == 1
    assert calls[0][0] == "scan.abc.progress"
    assert calls[0][1] == {"type": "progress"}


async def test_multiple_subscribers():
    """TC-EVENT-002: một event tới tất cả subscriber hợp lệ."""
    bus = EventBus()
    c1, h1 = _recorder()
    c2, h2 = _recorder()
    bus.subscribe("scan.abc.done", h1)
    bus.subscribe("scan.abc.done", h2)
    await bus.publish("scan.abc.done", {"type": "done"})
    assert len(c1) == 1
    assert len(c2) == 1


async def test_unsubscribe():
    """TC-EVENT-003: sau unsubscribe -> publish không gọi callback."""
    bus = EventBus()
    calls, handler = _recorder()
    unsub = bus.subscribe("scan.abc.done", handler)
    unsub()
    await bus.publish("scan.abc.done", {"type": "done"})
    assert calls == []


async def test_wildcard_segment():
    """TC-EVENT-004: '*' khớp đúng 1 segment."""
    bus = EventBus()
    calls, handler = _recorder()
    bus.subscribe("scan.*.progress", handler)
    await bus.publish("scan.abc.progress", {"x": 1})
    await bus.publish("scan.abc.done", {"x": 2})  # segment khác -> không khớp
    await bus.publish("scan.a.b.progress", {"x": 3})  # quá sâu -> không khớp
    assert len(calls) == 1
    assert calls[0][0] == "scan.abc.progress"


async def test_wildcard_hash():
    """'#' khớp mọi segment còn lại."""
    bus = EventBus()
    calls, handler = _recorder()
    bus.subscribe("scan.#", handler)
    await bus.publish("scan.abc.progress", {"a": 1})
    await bus.publish("scan.abc.item", {"a": 2})
    await bus.publish("other.topic", {"a": 3})
    assert len(calls) == 2


async def test_subscriber_failure_isolation():
    """TC-ERR-003: một subscriber throw -> các subscriber khác vẫn nhận event."""
    bus = EventBus()
    bad_calls: list = []
    good_calls: list = []

    async def bad(topic, message):
        bad_calls.append(message)
        raise RuntimeError("boom")

    async def good(topic, message):
        good_calls.append(message)

    bus.subscribe("scan.x", bad)
    bus.subscribe("scan.x", good)
    await bus.publish("scan.x", {"n": 1})

    assert len(bad_calls) == 1
    assert len(good_calls) == 1


def test_match_unit():
    assert _match("scan.abc.progress", "scan.abc.progress")
    assert _match("scan.*.progress", "scan.abc.progress")
    assert not _match("scan.*.progress", "scan.abc.done")
    assert _match("scan.#", "scan.a.b.c")
    assert not _match("scan.abc", "scan.abc.progress")
    assert not _match("scan.abc.progress", "scan.abc")


# UT-EV-001..004: _match edge cases


def test_match_exact():
    """UT-EV-001: exact match."""
    assert _match("scan.abc.progress", "scan.abc.progress")


def test_match_star_wrong_segment_count():
    """UT-EV-002: 'scan.progress' không match 'scan.abc.progress' (2 segment vs 3)."""
    assert not _match("scan.progress", "scan.abc.progress")


def test_match_hash_tail():
    """UT-EV-003: 'scan.#' match 'scan.abc.progress'."""
    assert _match("scan.#", "scan.abc.progress")


def test_match_no_match_different_topic():
    """UT-EV-004: 'scan.abc.progress' không match 'scan.abc.error'."""
    assert not _match("scan.abc.progress", "scan.abc.error")
