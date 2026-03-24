"""
ProductAliasRepository
======================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_alias import ProductAlias
from app.repositories.base import BaseRepository
from app.schemas.product_alias import ProductAliasCreateSchema


class ProductAliasRepository(BaseRepository[ProductAlias, ProductAliasCreateSchema, ProductAliasCreateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ProductAlias)

    async def get_by_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[ProductAlias]:
        stmt = (
            select(ProductAlias)
            .where(ProductAlias.product_id == product_id, ProductAlias.org_id == org_id)
            .order_by(ProductAlias.alias_text)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_text(
        self, alias_text: str, org_id: uuid.UUID
    ) -> ProductAlias | None:
        """Find alias by exact text match within tenant."""
        stmt = (
            select(ProductAlias)
            .where(
                ProductAlias.alias_text == alias_text,
                ProductAlias.org_id == org_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
