"""
InvoiceRepository
=================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice
from app.repositories.base import BaseRepository
from app.schemas.invoice import InvoiceCreateSchema, InvoiceUpdateSchema


class InvoiceRepository(BaseRepository[Invoice, InvoiceCreateSchema, InvoiceUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Invoice)

    async def get_by_supplier(
        self, supplier_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(
                Invoice.supplier_id == supplier_id,
                Invoice.org_id == org_id,
                Invoice.deleted_at.is_(None),
            )
            .order_by(Invoice.invoice_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_items(
        self, invoice_id: uuid.UUID, org_id: uuid.UUID
    ) -> Optional[Invoice]:
        """Eager-load invoice line items."""
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.items))
            .where(
                Invoice.id == invoice_id,
                Invoice.org_id == org_id,
                Invoice.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_invoice_number(
        self, invoice_number: str, org_id: uuid.UUID
    ) -> Optional[Invoice]:
        stmt = (
            select(Invoice)
            .where(
                Invoice.invoice_number == invoice_number,
                Invoice.org_id == org_id,
                Invoice.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
