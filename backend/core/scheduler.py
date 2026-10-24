from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class Scheduler:
    """Bọc APScheduler — đăng ký scan tự động theo cron từ manifest.default_schedule.

    Scan tự động chạy thẳng qua executor (không qua REST) và broadcast kết quả
    qua event_bus tới mọi client đang mở (mục 5.2 docs/architecture/backend.md).
    """

    def __init__(self, registry: dict) -> None:
        self.registry = registry
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._started = False

    def start(self) -> None:
        self._scheduler = AsyncIOScheduler()
        for module_id, manifest in self.registry.items():
            if not manifest.default_schedule or not manifest.enabled:
                continue
            if not manifest.default_schedule.strip():
                continue
            self._scheduler.add_job(
                _scheduled_scan_job,
                trigger=CronTrigger.from_crontab(manifest.default_schedule),
                args=[manifest],
                id=f"scan-{module_id}",
                name=f"Scan tự động: {manifest.display_name}",
                misfire_grace_time=60,
                replace_existing=True,
            )
            logger.info("Schedule đã đăng ký: %s (%s)", module_id, manifest.default_schedule)
        if self._scheduler.get_jobs():
            self._scheduler.start()
            self._started = True

    def shutdown(self) -> None:
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False


async def _scheduled_scan_job(manifest) -> None:
    from core.executor import dispatch_scan

    await dispatch_scan(manifest)