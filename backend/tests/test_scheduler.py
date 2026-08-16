from __future__ import annotations

from core.scheduler import Scheduler, _scheduled_scan_job


class _FakeManifest:
    def __init__(self, module_id, schedule=None):
        self.id = module_id
        self.display_name = "Fake Module"
        self.default_schedule = schedule
        self.enabled = True


def test_scheduler_no_schedule_no_jobs():
    """TC-SCHED-001: không cấu hình schedule -> không tạo job, scheduler không start."""
    sched = Scheduler({"a": _FakeManifest("a", None)})
    sched.start()
    try:
        assert sched._scheduler is not None
        assert sched._scheduler.get_jobs() == []
        assert sched._started is False
    finally:
        sched.shutdown()


def test_scheduler_registers_scheduled_job(monkeypatch):
    """TC-SCHED-002: schedule hợp lệ -> job được đăng ký."""
    from core import scheduler as sched_mod

    # Không start event loop thật để test đăng ký job một cách deterministic
    monkeypatch.setattr(sched_mod.AsyncIOScheduler, "start", lambda self: None)
    monkeypatch.setattr(sched_mod.AsyncIOScheduler, "shutdown", lambda self, wait=True: None)

    sched = sched_mod.Scheduler({"a": _FakeManifest("a", "0 * * * *")})
    sched.start()
    try:
        jobs = sched._scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "scan-a"
        assert sched._started is True
    finally:
        sched.shutdown()


async def test_scheduler_job_triggers_dispatch(monkeypatch):
    """TC-SCHED-003: job execute -> dispatch_scan được gọi (không chờ real time)."""
    from core import executor as executor_mod

    calls: list = []

    async def fake_dispatch(manifest):
        calls.append(manifest.id)
        return "scan-id"

    monkeypatch.setattr(executor_mod, "dispatch_scan", fake_dispatch)
    manifest = _FakeManifest("a", "0 * * * *")
    await _scheduled_scan_job(manifest)
    assert calls == ["a"]
