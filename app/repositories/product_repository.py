"""
ProductRepository
=================
Data access layer for products.
Equivalent to Laravel's ProductRepository implementing ProductRepositoryInterface.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.repositories.base import BaseRepository
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema


class ProductRepository(BaseRepository[Product, ProductCreateSchema, ProductUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Product)

    async def get_by_slug(
        self, slug: str, org_id: uuid.UUID
    ) -> Product | None:
        """Find a product by its generated slug within a tenant."""
        stmt = (
            select(Product)
            .where(Product.slug == slug, Product.org_id == org_id)
            .where(Product.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sku(
        self, sku: str, org_id: uuid.UUID
    ) -> Product | None:
        """Find a product by SKU within a tenant."""
        stmt = (
            select(Product)
            .where(Product.sku == sku, Product.org_id == org_id)
            .where(Product.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(
        self, query: str, org_id: uuid.UUID, limit: int = 20
    ) -> list[Product]:
        """
        Full-text iLIKE search on product name.
        In production, replace with pg_trgm or full-text-search index.
        """
        stmt = (
            select(Product)
            .where(
                Product.name.ilike(f"%{query}%"),
                Product.org_id == org_id,
                Product.deleted_at.is_(None),
            )
            .order_by(Product.name)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_aliases(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> Product | None:
        """Eager-load product aliases in a single query."""
        stmt = (
            select(Product)
            .options(selectinload(Product.aliases))
            .where(
                Product.id == product_id,
                Product.org_id == org_id,
                Product.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_category(
        self, category: str, org_id: uuid.UUID
    ) -> list[Product]:
        """Return all products in a specific category."""
        stmt = (
            select(Product)
            .where(
                Product.category == category,
                Product.org_id == org_id,
                Product.deleted_at.is_(None),
            )
            .order_by(Product.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
