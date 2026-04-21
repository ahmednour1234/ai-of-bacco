"""
app/tasks/celery_app.py
------------------------
Celery application factory.
Import this module where tasks are declared; do NOT import the full app stack.
"""

from celery import Celery
from celery.schedules import crontab as celery_crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "qumta",
    broker=settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.document_tasks",
        "app.tasks.product_tasks",
        "app.tasks.price_tasks",
        # Scraper tasks — separate database, same broker/worker pool
        "scraper.tasks.scraper_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # ── Celery Beat schedule ───────────────────────────────────────────────────
    beat_schedule={
        # Scrape the example source every day at 02:00 UTC
        "scrape-example-source-daily": {
            "task": "scraper.run_scraper",
            "schedule": celery_crontab(hour=2, minute=0),
            "args": ("Example Store",),
        },
        # Scrape El Buroj (إنارة / Lighting category) every day at 03:00 UTC
        "scrape-elburoj-lighting-daily": {
            "task": "scraper.run_scraper",
            "schedule": celery_crontab(hour=3, minute=0),
            "args": ("El Buroj",),
        },
        # Sync all unsynced scraper products to the external API every hour
        "sync-scraper-products-hourly": {
            "task": "scraper.sync_products",
            "schedule": celery_crontab(minute=0),
        },
    },
)
