"""
scraper/repositories/sync_log_repository.py
--------------------------------------------
CRUD for ScraperSyncLog audit records.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.models.sync_log import ScraperSyncLog
from scraper.repositories.base import BaseScraperRepository


class ScraperSyncLogRepository(BaseScraperRepository[ScraperSyncLog]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ScraperSyncLog)

    async def get_logs_for_product(
        self, scraper_product_id: int, limit: int = 50
    ) -> list[ScraperSyncLog]:
        result = await self.db.execute(
            select(ScraperSyncLog)
            .where(ScraperSyncLog.scraper_product_id == scraper_product_id)
            .order_by(ScraperSyncLog.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def log_attempt(
        self,
        scraper_product_id: int,
        sync_status: str,
        request_payload: str | None = None,
        response_body: str | None = None,
        synced_at=None,
    ) -> ScraperSyncLog:
        return await self.create(
            {
                "scraper_product_id": scraper_product_id,
                "sync_status": sync_status,
                "request_payload": request_payload,
                "response_body": response_body,
                "synced_at": synced_at,
            }
        )
