"""
scraper/repositories/source_repository.py
------------------------------------------
CRUD + get-or-create helpers for ScraperSource.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.models.source import ScraperSource
from scraper.repositories.base import BaseScraperRepository


class ScraperSourceRepository(BaseScraperRepository[ScraperSource]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ScraperSource)

    async def get_by_name(self, name: str) -> ScraperSource | None:
        result = await self.db.execute(
            select(ScraperSource).where(ScraperSource.name == name)
        )
        return result.scalar_one_or_none()

    async def get_active_sources(self) -> list[ScraperSource]:
        result = await self.db.execute(
            select(ScraperSource).where(ScraperSource.active.is_(True))
        )
        return list(result.scalars().all())

    async def get_or_create(self, name: str, base_url: str) -> ScraperSource:
        """Return existing source by name or create it."""
        existing = await self.get_by_name(name)
        if existing:
            return existing
        return await self.create({"name": name, "base_url": base_url, "active": True})
