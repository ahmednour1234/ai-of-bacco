"""
InvoiceItemRepository
=====================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice_item import InvoiceItem
from app.repositories.base import BaseRepository
from app.schemas.invoice_item import InvoiceItemCreateSchema, InvoiceItemUpdateSchema


class InvoiceItemRepository(BaseRepository[InvoiceItem, InvoiceItemCreateSchema, InvoiceItemUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, InvoiceItem)

    async def get_by_invoice(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        stmt = (
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == invoice_id)
            .order_by(InvoiceItem.line_number)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_unmatched(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        """Return items that have no matched product yet."""
        stmt = (
            select(InvoiceItem)
            .where(
                InvoiceItem.invoice_id == invoice_id,
                InvoiceItem.product_id.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
