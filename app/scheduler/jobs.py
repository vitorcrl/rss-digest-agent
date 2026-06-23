import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_daily_digest() -> None:
    from app.core.database import AsyncSessionFactory
    from app.services.digest_service import DigestService

    async with AsyncSessionFactory() as session:
        try:
            digest = await DigestService(session).run()
            logger.info("Daily digest completed: status=%s", digest.status.value)
        except Exception as exc:
            logger.exception("Daily digest job failed: %s", exc)


def start_scheduler() -> None:
    scheduler.add_job(
        func=_run_daily_digest,
        trigger=CronTrigger(
            hour=settings.DIGEST_CRON_HOUR,
            minute=0,
            timezone=settings.DIGEST_CRON_TIMEZONE,
        ),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler started — daily digest at %02dh %s", settings.DIGEST_CRON_HOUR, settings.DIGEST_CRON_TIMEZONE)


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
