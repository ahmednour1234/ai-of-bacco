"""
scraper/repositories/category_repository.py
--------------------------------------------
CRUD + get-or-create helpers for ScraperCategory.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.models.category import ScraperCategory
from scraper.repositories.base import BaseScraperRepository


class ScraperCategoryRepository(BaseScraperRepository[ScraperCategory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ScraperCategory)

    async def get_by_source_and_external_id(
        self, source_id: int, external_id: str
    ) -> ScraperCategory | None:
        result = await self.db.execute(
            select(ScraperCategory).where(
                ScraperCategory.source_id == source_id,
                ScraperCategory.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_source_and_name(
        self, source_id: int, name: str
    ) -> ScraperCategory | None:
        result = await self.db.execute(
            select(ScraperCategory).where(
                ScraperCategory.source_id == source_id,
                ScraperCategory.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        source_id: int,
        name: str,
        external_id: str | None = None,
        url: str | None = None,
    ) -> ScraperCategory:
        """
        Return an existing category matched by external_id (if given) or name,
        or create a new one.
        """
        existing: ScraperCategory | None = None
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
                "url": url,
            }
        )
