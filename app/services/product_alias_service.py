"""
app/services/product_alias_service.py
---------------------------------------
Business logic for product aliases.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.product_alias_repository import ProductAliasRepository
from app.schemas.product_alias import ProductAliasCreateSchema, ProductAliasResponseSchema
from app.services.base import BaseService


class ProductAliasService(BaseService[ProductAliasRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ProductAliasRepository(db))

    async def create_alias(
        self,
        schema: ProductAliasCreateSchema,
        product_id: uuid.UUID,
        org_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> ProductAliasResponseSchema:
        data = {
            **schema.model_dump(),
            "product_id": product_id,
            "org_id": org_id,
            "owner_id": owner_id,
        }
        alias = await self.repo.create_from_dict(data)
        return ProductAliasResponseSchema.model_validate(alias)

    async def list_aliases(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[ProductAliasResponseSchema]:
        aliases = await self.repo.get_by_product(product_id)
        return [ProductAliasResponseSchema.model_validate(a) for a in aliases]
