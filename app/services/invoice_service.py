"""
InvoiceService
==============
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceCreateSchema, InvoiceUpdateSchema, InvoiceResponseSchema, InvoiceListItemSchema
from app.services.base import BaseService


class InvoiceService(BaseService[InvoiceRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(InvoiceRepository(db))

    async def create_invoice(
        self, schema: InvoiceCreateSchema, org_id: uuid.UUID, owner_id: uuid.UUID
    ) -> InvoiceResponseSchema:
        data = {**schema.model_dump(), "org_id": org_id, "owner_id": owner_id}
        invoice = await self.repo.create_from_dict(data)
        return InvoiceResponseSchema.model_validate(invoice)

    async def get_invoice(self, invoice_id: uuid.UUID, org_id: uuid.UUID) -> InvoiceResponseSchema:
        invoice = await self.get_by_id_or_fail(invoice_id, org_id, "Invoice")
        return InvoiceResponseSchema.model_validate(invoice)

    async def list_invoices(
        self, org_id: uuid.UUID, page: int = 1, per_page: int = 15
    ) -> tuple[list[InvoiceListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id)
        return [InvoiceListItemSchema.model_validate(i) for i in items], total

    async def update_invoice(
        self, invoice_id: uuid.UUID, schema: InvoiceUpdateSchema, org_id: uuid.UUID
    ) -> InvoiceResponseSchema:
        invoice = await self.get_by_id_or_fail(invoice_id, org_id, "Invoice")
        updated = await self.repo.update(invoice, schema)
        return InvoiceResponseSchema.model_validate(updated)

    async def delete_invoice(self, invoice_id: uuid.UUID, org_id: uuid.UUID) -> None:
        await self.soft_delete_or_fail(invoice_id, org_id, "Invoice")
