"""
scraper/services/scrape_service.py
------------------------------------
Base class for all concrete scraper implementations.

Concrete scrapers inherit from BaseScrapeService and override
`source_name`, `source_base_url`, and `_fetch_raw_products()`.
The base class handles:
  - Ensuring the source exists in the scraper DB
  - Resolving categories and brands (get-or-create)
  - Calling upsert_product for each scraped product
  - Returning a summary dict {scraped, inserted, updated}

Example:
    class MyStoreScraper(BaseScrapeService):
        source_name = "My Store"
        source_base_url = "https://mystore.example.com"

        async def _fetch_raw_products(self) -> list[dict]:
            async with httpx.AsyncClient() as client:
                resp = await client.get(...)
            return parse(resp)

    async with ScraperSessionLocal() as db:
        await db.begin()
        summary = await MyStoreScraper(db).run()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from scraper.repositories.brand_repository import ScraperBrandRepository
from scraper.repositories.category_repository import ScraperCategoryRepository
from scraper.repositories.product_repository import ScraperProductRepository
from scraper.repositories.source_repository import ScraperSourceRepository

logger = logging.getLogger(__name__)


class BaseScrapeService(ABC):
    """
    Abstract base class for all website scrapers.

    Each concrete scraper must declare `source_name` and `source_base_url`
    as class attributes, and implement `_fetch_raw_products()`.

    The raw product dict fed to `_save_product()` should contain at minimum:
        - source_url (str, required)
        - name       (str, required)
    Optional keys:
        - external_id, sku, description, specifications, price (Decimal|float|str),
          raw_data (str/JSON), hash (str), scraper_category_id (int),
          scraper_brand_id (int)

    Categories and brands can be resolved before calling _save_product via the
    helper methods `_get_or_create_category()` and `_get_or_create_brand()`.
    """

    #: Override in subclass — must match the unique name in scraper_sources
    source_name: str = ""
    source_base_url: str = ""

    def __init__(self, db: AsyncSession) -> None:
        if not self.source_name:
            raise ValueError(
                f"{self.__class__.__name__} must define `source_name` as a class attribute."
            )
        self.db = db
        self._source_repo = ScraperSourceRepository(db)
        self._category_repo = ScraperCategoryRepository(db)
        self._brand_repo = ScraperBrandRepository(db)
        self._product_repo = ScraperProductRepository(db)
        self._source_id: int | None = None

    # ── Public entry-point ─────────────────────────────────────────────────────

    async def run(self) -> dict[str, int]:
        """
        Execute the full scrape cycle for this source.

        Returns:
            {"scraped": N, "inserted": N, "updated": N, "errors": N}
        """
        source = await self._source_repo.get_or_create(
            self.source_name, self.source_base_url
        )
        self._source_id = source.id

        raw_products = await self._fetch_raw_products()

        stats = {"scraped": len(raw_products), "inserted": 0, "updated": 0, "errors": 0}

        for raw in raw_products:
            try:
                _product, created = await self._save_product(raw)
                if created:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1
            except Exception as exc:
                stats["errors"] += 1
                logger.exception(
                    "Error saving product from %s: %s", self.source_name, exc
                )

        await self.db.commit()
        logger.info(
            "[%s] Scrape complete — %s",
            self.source_name,
            stats,
        )
        return stats

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    async def _fetch_raw_products(self) -> list[dict[str, Any]]:
        """
        Fetch products from the external website and return a list of raw dicts.
        Each dict must include at least ``source_url`` and ``name``.
        """

    # ── Helpers available to subclasses ───────────────────────────────────────

    async def _save_product(
        self, raw: dict[str, Any]
    ) -> tuple[Any, bool]:
        """Inject source_id then upsert the product."""
        raw["source_id"] = self._source_id
        return await self._product_repo.upsert_product(raw)

    async def _get_or_create_category(
        self,
        name: str,
        external_id: str | None = None,
        url: str | None = None,
    ) -> int:
        """Resolve or create a category and return its id."""
        if self._source_id is None:
            raise RuntimeError("_source_id not set — call run() or set it manually.")
        category = await self._category_repo.get_or_create(
            source_id=self._source_id,
            name=name,
            external_id=external_id,
            url=url,
        )
        return category.id

    async def _get_or_create_brand(
        self,
        name: str,
        external_id: str | None = None,
    ) -> int:
        """Resolve or create a brand and return its id."""
        if self._source_id is None:
            raise RuntimeError("_source_id not set — call run() or set it manually.")
        brand = await self._brand_repo.get_or_create(
            source_id=self._source_id,
            name=name,
            external_id=external_id,
        )
        return brand.id
