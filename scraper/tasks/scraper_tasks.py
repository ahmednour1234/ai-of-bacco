"""
scraper/tasks/scraper_tasks.py
---------------------------------
Celery tasks for the scraper system.

These tasks are registered on the SAME Celery app as the main application
(app.tasks.celery_app) so they share the same Redis broker and are visible
to the same worker pool.  They bridge from Celery's synchronous task
environment into the async scraper services using asyncio.run().

Beat schedule (added to celery_app.conf.beat_schedule):
  - scrape-example-source-daily  → run_scraper_task("Example Store") @ 02:00 UTC
  - sync-scraper-products-hourly → sync_products_task()               @ :00 every hour

Running the worker (from project root):
    celery -A app.tasks.celery_app worker -l info
    celery -A app.tasks.celery_app beat   -l info   # for scheduled tasks

Triggering manually:
    from scraper.tasks.scraper_tasks import run_scraper_task, sync_products_task
    run_scraper_task.delay("Example Store")
    sync_products_task.delay()
"""

from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Registry of available scrapers ────────────────────────────────────────────
# Map source_name → scraper class.  Add new scrapers here.

def _get_scraper_registry() -> dict[str, type]:
    """
    Lazy import to avoid circular imports and heavy module loading at task
    registration time.  The registry maps source_name → scraper class.
    """
    from scraper.scrapers.example_scraper import ExampleStoreScraper
    from scraper.scrapers.elburoj_scraper import ElBurojScraper

    return {
        ExampleStoreScraper.source_name: ExampleStoreScraper,
        ElBurojScraper.source_name: ElBurojScraper,
    }


# ── Scrape task ────────────────────────────────────────────────────────────────

@celery_app.task(
    name="scraper.run_scraper",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
)
def run_scraper_task(self, source_name: str) -> dict:
    """
    Run the scraper for a given source_name.

    Args:
        source_name: Must match a key in the scraper registry.

    Returns:
        Stats dict: {"scraped": N, "inserted": N, "updated": N, "errors": N}
    """
    registry = _get_scraper_registry()
    scraper_cls = registry.get(source_name)
    if scraper_cls is None:
        known = list(registry.keys())
        raise ValueError(
            f"Unknown scraper source: '{source_name}'. Known sources: {known}"
        )

    async def _run() -> dict:
        from scraper.core.database import ScraperSessionLocal

        async with ScraperSessionLocal() as db:
            scraper = scraper_cls(db)
            return await scraper.run()

    try:
        stats = asyncio.run(_run())
        logger.info("[run_scraper_task] %s — %s", source_name, stats)
        return stats
    except Exception as exc:
        logger.exception("[run_scraper_task] %s failed: %s", source_name, exc)
        raise self.retry(exc=exc)


# ── Sync task ──────────────────────────────────────────────────────────────────

@celery_app.task(
    name="scraper.sync_products",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def sync_products_task(self, batch_size: int | None = None) -> dict:
    """
    Send all pending (is_synced=False) scraper products to the external API.

    Args:
        batch_size: Override the default SCRAPER_SYNC_BATCH_SIZE setting.

    Returns:
        Stats dict: {"processed": N, "succeeded": N, "failed": N}
    """
    async def _run() -> dict:
        from scraper.core.database import ScraperSessionLocal
        from scraper.services.sync_service import SyncService

        async with ScraperSessionLocal() as db:
            service = SyncService(db)
            return await service.sync_pending(batch_size=batch_size)

    try:
        stats = asyncio.run(_run())
        logger.info("[sync_products_task] %s", stats)
        return stats
    except Exception as exc:
        logger.exception("[sync_products_task] failed: %s", exc)
        raise self.retry(exc=exc)
