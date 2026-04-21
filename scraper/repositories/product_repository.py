"""
scraper/repositories/product_repository.py
-------------------------------------------
ScraperProduct CRUD with dedup-aware upsert.

Duplicate detection priority (matching the business rules):
    1. source_id + external_id   (if external_id provided)
    2. source_id + source_url
    3. source_id + sku           (if sku provided)

upsert_product() returns (product, created: bool).
When an existing product is found its fields are updated in-place and
is_synced is reset to False so the sync service will re-send the update.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.models.product import ScraperProduct
from scraper.repositories.base import BaseScraperRepository


class ScraperProductRepository(BaseScraperRepository[ScraperProduct]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ScraperProduct)

    # ── Lookup helpers ─────────────────────────────────────────────────────────

    async def _find_by_source_and_external_id(
        self, source_id: int, external_id: str
    ) -> ScraperProduct | None:
        result = await self.db.execute(
            select(ScraperProduct).where(
                ScraperProduct.source_id == source_id,
                ScraperProduct.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def _find_by_source_and_url(
        self, source_id: int, source_url: str
    ) -> ScraperProduct | None:
        result = await self.db.execute(
            select(ScraperProduct).where(
                ScraperProduct.source_id == source_id,
                ScraperProduct.source_url == source_url,
            )
        )
        return result.scalar_one_or_none()

    async def _find_by_source_and_sku(
        self, source_id: int, sku: str
    ) -> ScraperProduct | None:
        result = await self.db.execute(
            select(ScraperProduct).where(
                ScraperProduct.source_id == source_id,
                ScraperProduct.sku == sku,
            )
        )
        return result.scalar_one_or_none()

    # ── Dedup upsert ───────────────────────────────────────────────────────────

    async def upsert_product(
        self, data: dict[str, Any]
    ) -> tuple[ScraperProduct, bool]:
        """
        Insert or update a scraped product.

        Returns:
            (product, created) — created=True if a new row was inserted.

        Lookup order:
            1. source_id + external_id
            2. source_id + source_url
            3. source_id + sku
        """
        source_id: int = data["source_id"]
        external_id: str | None = data.get("external_id")
        source_url: str = data["source_url"]
        sku: str | None = data.get("sku")

        existing: ScraperProduct | None = None

        # Priority 1: source_id + external_id
        if external_id:
            existing = await self._find_by_source_and_external_id(
                source_id, external_id
            )

        # Priority 2: source_id + source_url
        if not existing:
            existing = await self._find_by_source_and_url(source_id, source_url)

        # Priority 3: source_id + sku
        if not existing and sku:
            existing = await self._find_by_source_and_sku(source_id, sku)

        if existing:
            # Update all mutable fields; mark as unsynced so the sync service
            # will send the updated version to the external API.
            update_fields = {
                k: v
                for k, v in data.items()
                if k
                not in ("id", "source_id", "created_at", "is_synced", "synced_at")
            }
            update_fields["is_synced"] = False
            update_fields["last_scraped_at"] = datetime.now(timezone.utc)
            return await self.update(existing, update_fields), False

        # New product
        data.setdefault("is_synced", False)
        data["last_scraped_at"] = datetime.now(timezone.utc)
        product = await self.create(data)
        return product, True

    # ── Sync helpers ───────────────────────────────────────────────────────────

    async def get_unsynced(self, limit: int = 100) -> list[ScraperProduct]:
        """Return up to `limit` products where is_synced = False."""
        result = await self.db.execute(
            select(ScraperProduct)
            .where(ScraperProduct.is_synced.is_(False))
            .order_by(ScraperProduct.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_synced(self, product: ScraperProduct) -> ScraperProduct:
        """Mark a single product as synced."""
        now = datetime.now(timezone.utc)
        return await self.update(
            product, {"is_synced": True, "synced_at": now}
        )
