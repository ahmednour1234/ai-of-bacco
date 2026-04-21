"""
scraper/repositories/brand_repository.py
-----------------------------------------
CRUD + get-or-create helpers for ScraperBrand.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.models.brand import ScraperBrand
from scraper.repositories.base import BaseScraperRepository


class ScraperBrandRepository(BaseScraperRepository[ScraperBrand]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ScraperBrand)

    async def get_by_source_and_external_id(
        self, source_id: int, external_id: str
    ) -> ScraperBrand | None:
        result = await self.db.execute(
            select(ScraperBrand).where(
                ScraperBrand.source_id == source_id,
                ScraperBrand.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_source_and_name(
        self, source_id: int, name: str
    ) -> ScraperBrand | None:
        result = await self.db.execute(
            select(ScraperBrand).where(
                ScraperBrand.source_id == source_id,
                ScraperBrand.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        source_id: int,
        name: str,
        external_id: str | None = None,
    ) -> ScraperBrand:
        """
        Return an existing brand matched by external_id (if given) or name,
        or create a new one.
        """
        existing: ScraperBrand | None = None
        if external_id:
            existing = await self.get_by_source_and_external_id(source_id, external_id)
        if not existing:
            existing = await self.get_by_source_and_name(source_id, name)
        if existing:
            return existing
        return await self.create(
            {
                "source_id": source_id,
                "external_id": external_id,
                "name": name,
            }
        )
