"""
ExtractedItemRepository
=======================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extracted_item import ExtractedItem
from app.repositories.base import BaseRepository
from app.schemas.extracted_item import ExtractedItemUpdateSchema


class ExtractedItemRepository(BaseRepository[ExtractedItem, ExtractedItemUpdateSchema, ExtractedItemUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ExtractedItem)

    async def get_by_document(
        self, document_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[ExtractedItem]:
        stmt = (
            select(ExtractedItem)
            .where(
                ExtractedItem.document_id == document_id,
                ExtractedItem.org_id == org_id,
            )
            .order_by(ExtractedItem.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_unmatched(self, org_id: uuid.UUID) -> list[ExtractedItem]:
        """Return all unmatched (no product link) items pending review."""
        stmt = (
            select(ExtractedItem)
            .where(
                ExtractedItem.matched_product_id.is_(None),
                ExtractedItem.is_reviewed.is_(False),
                ExtractedItem.org_id == org_id,
            )
            .order_by(ExtractedItem.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[ExtractedItem]:
        stmt = (
            select(ExtractedItem)
            .where(
                ExtractedItem.matched_product_id == product_id,
                ExtractedItem.org_id == org_id,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
