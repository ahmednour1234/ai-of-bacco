"""
SupplierService
===============
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier import SupplierCreateSchema, SupplierUpdateSchema, SupplierResponseSchema, SupplierListItemSchema
from app.services.base import BaseService
from app.utils.slugify import generate_slug


class SupplierService(BaseService[SupplierRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(SupplierRepository(db))

    async def create_supplier(
        self, schema: SupplierCreateSchema, org_id: uuid.UUID, owner_id: uuid.UUID
    ) -> SupplierResponseSchema:
        slug = generate_slug(schema.name)
        if await self.repo.get_by_slug(slug, org_id):
            raise ConflictException(f"Supplier '{schema.name}' already exists.")
        data = {**schema.model_dump(), "slug": slug, "org_id": org_id, "owner_id": owner_id}
        supplier = await self.repo.create_from_dict(data)
        return SupplierResponseSchema.model_validate(supplier)

    async def get_supplier(self, supplier_id: uuid.UUID, org_id: uuid.UUID) -> SupplierResponseSchema:
        supplier = await self.get_by_id_or_fail(supplier_id, org_id, "Supplier")
        return SupplierResponseSchema.model_validate(supplier)

    async def list_suppliers(
        self, org_id: uuid.UUID, page: int = 1, per_page: int = 15
    ) -> tuple[list[SupplierListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id)
        return [SupplierListItemSchema.model_validate(s) for s in items], total

    async def update_supplier(
        self, supplier_id: uuid.UUID, schema: SupplierUpdateSchema, org_id: uuid.UUID
    ) -> SupplierResponseSchema:
        supplier = await self.get_by_id_or_fail(supplier_id, org_id, "Supplier")
        updated = await self.repo.update(supplier, schema)
        return SupplierResponseSchema.model_validate(updated)

    async def delete_supplier(self, supplier_id: uuid.UUID, org_id: uuid.UUID) -> None:
        await self.soft_delete_or_fail(supplier_id, org_id, "Supplier")
