from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings
from .crawler.royal_caribbean import RoyalCaribbeanCrawler
from .database import SessionLocal
from .services import snapshot_service

logger = logging.getLogger(__name__)


class CrawlScheduler:
    """Periodically triggers the crawler and persists results."""

    def __init__(self) -> None:
        self._timezone = self._resolve_timezone(settings.scheduler_timezone)
        self._scheduler = BackgroundScheduler(timezone=self._timezone)
        self._crawler = RoyalCaribbeanCrawler()
        self._job = None

    def _resolve_timezone(self, configured: str) -> ZoneInfo:
        fallback = "Etc/UTC"
        try:
            return ZoneInfo(configured)
        except ZoneInfoNotFoundError:
            logging.getLogger(__name__).warning(
                "Timezone %s not found; falling back to %s", configured, fallback
            )
            return ZoneInfo(fallback)

    def start(self) -> None:
        if not settings.enable_scheduler:
            logger.warning("Scheduler is disabled via configuration")
            return
        if self._scheduler.running:
            return

        trigger = IntervalTrigger(minutes=settings.crawl_interval_minutes, timezone=self._timezone)
        self._job = self._scheduler.add_job(
            self._run_job,
            trigger=trigger,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(timezone.utc),
            id="royal-caribbean-crawl",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "Scheduler started with %s minute interval", settings.crawl_interval_minutes
        )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def _run_job(self) -> None:
        logger.info("Executing scheduled crawl run")
        db = SessionLocal()
        try:
            snapshot = self._crawler.scrape()
            snapshot_service.create_snapshot(db, snapshot)
            logger.info("Snapshot stored at %s", snapshot.scraped_at.isoformat())
        except Exception as exc:  # pragma: no cover - scheduler safety net
            logger.exception("Scheduled crawl failed: %s", exc)
        finally:
            db.close()


scheduler = CrawlScheduler()
