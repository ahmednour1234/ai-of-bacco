"""
scraper/models/__init__.py
---------------------------
Import all scraper ORM models here so that ScraperBase.metadata is fully
populated before Alembic's autogenerate or any migration runs.
"""

from scraper.models.brand import ScraperBrand
from scraper.models.category import ScraperCategory
from scraper.models.product import ScraperProduct
from scraper.models.source import ScraperSource
from scraper.models.sync_log import ScraperSyncLog

__all__ = [
    "ScraperSource",
    "ScraperCategory",
    "ScraperBrand",
    "ScraperProduct",
    "ScraperSyncLog",
]
