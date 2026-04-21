"""
scraper/scrapers/example_scraper.py
--------------------------------------
A concrete scraper example targeting a fictional JSON product API.

Replace the URL, JSON keys, and parsing logic to match your real source.

This example demonstrates:
  - Fetching paginated JSON from an external catalogue API
  - Resolving category and brand via get-or-create helpers
  - Computing a content hash to detect changes without re-processing unchanged products
  - Passing raw_data (full JSON blob) for debugging

To run manually (from project root):

    python -c "
    import asyncio
    from scraper.core.database import ScraperSessionLocal
    from scraper.scrapers.example_scraper import ExampleStoreScraper

    async def main():
        async with ScraperSessionLocal() as db:
            stats = await ExampleStoreScraper(db).run()
            print(stats)

    asyncio.run(main())
    "
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from scraper.scrapers.base_scraper import BaseScraper
from scraper.services.scrape_service import BaseScrapeService

logger = logging.getLogger(__name__)


class ExampleStoreScraper(BaseScrapeService, BaseScraper):
    """
    Example scraper for a fictional JSON product catalogue API.

    The source API is assumed to return pages of products at:
        GET /api/products?page=1&per_page=50

    Each item in the response looks like:
        {
            "id": "EXT-001",
            "url": "https://example-store.com/products/widget",
            "sku": "WGT-100",
            "name": "Super Widget",
            "category": {"id": "CAT-1", "name": "Widgets"},
            "brand": {"id": "BRD-1", "name": "ACME"},
            "description": "...",
            "specs": "Weight: 100g ...",
            "price": "19.99"
        }
    """

    source_name = "Example Store"
    source_base_url = "https://example-store.com"

    _api_base = "https://example-store.com/api"
    _page_size = 50

    # ── BaseScrapeService contract ─────────────────────────────────────────────

    async def _fetch_raw_products(self) -> list[dict[str, Any]]:
        await self._init_client()
        try:
            return await self._fetch_all_pages()
        finally:
            await self._close_client()

    # ── Internal pagination ────────────────────────────────────────────────────

    async def _fetch_all_pages(self) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        page = 1

        while True:
            data = await self._get_json(
                f"{self._api_base}/products",
                params={"page": page, "per_page": self._page_size},
            )
            items: list[dict] = data.get("data", data) if isinstance(data, dict) else data
            if not items:
                break

            for item in items:
                raw = await self._parse_item(item)
                if raw:
                    products.append(raw)

            # Stop if the page returned fewer items than requested
            if len(items) < self._page_size:
                break
            page += 1

        return products

    async def _parse_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Transform a raw API item into the dict expected by upsert_product."""
        try:
            # Resolve category
            category_id: int | None = None
            if cat := item.get("category"):
                category_id = await self._get_or_create_category(
                    name=cat["name"],
                    external_id=str(cat.get("id", "")),
                )

            # Resolve brand
            brand_id: int | None = None
            if brand := item.get("brand"):
                brand_id = await self._get_or_create_brand(
                    name=brand["name"],
                    external_id=str(brand.get("id", "")),
                )

            # Content hash — compare against stored hash to skip unchanged products
            content = json.dumps(
                {k: item.get(k) for k in ("name", "price", "description", "specs")},
                sort_keys=True,
            )
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            return {
                "external_id": str(item["id"]) if item.get("id") else None,
                "source_url": item["url"],
                "sku": item.get("sku"),
                "name": item["name"],
                "description": item.get("description"),
                "specifications": item.get("specs"),
                "price": item.get("price"),
                "raw_data": json.dumps(item),
                "hash": content_hash,
                "scraper_category_id": category_id,
                "scraper_brand_id": brand_id,
            }
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed product item: %s — %s", item, exc)
            return None
