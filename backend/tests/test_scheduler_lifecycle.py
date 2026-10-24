from __future__ import annotations

import pytest

from core.scheduler import Scheduler


class _FakeManifest:
    def __init__(self, module_id, schedule=None, enabled=True):
        self.id = module_id
        self.display_name = "Fake Module"
        self.version = "1.0"
        self.default_schedule = schedule
        self.enabled = enabled
        self.scanner_cls = None


def test_scheduler_no_schedule_no_jobs():
    """CL-SCH-001: Module không có default_schedule -> APScheduler không có job."""
    sched = Scheduler({"a": _FakeManifest("a", None)})
    sched.start()
    try:
        assert sched._scheduler is not None
        assert sched._scheduler.get_jobs() == []
        assert sched._started is False
    finally:
        sched.shutdown()


def test_scheduler_has_job_when_schedule_set(monkeypatch):
    """CL-SCH-002: Module có default_schedule -> job registered trong APScheduler."""
    from core import scheduler as sched_mod

    monkeypatch.setattr(sched_mod.AsyncIOScheduler, "start", lambda self: None)
    monkeypatch.setattr(sched_mod.AsyncIOScheduler, "shutdown", lambda self, wait=True: None)

    sched = sched_mod.Scheduler({"a": _FakeManifest("a", "0 * * * *")})
    sched.start()
    try:
        jobs = sched._scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "scan-a"
    finally:
        sched.shutdown()


async def test_scheduled_job_triggers_dispatch(monkeypatch):
    """CL-SCH-003: Mock APScheduler trigger job -> dispatch_scan được gọi."""
    from core import executor as executor_mod

    calls: list = []

    async def fake_dispatch(manifest):
        calls.append(manifest.id)
        return "scan-id"

    monkeypatch.setattr(executor_mod, "dispatch_scan", fake_dispatch)

    from core.scheduler import _scheduled_scan_job

    await _scheduled_scan_job(_FakeManifest("a", "0 * * * *"))
    assert calls == ["a"]
