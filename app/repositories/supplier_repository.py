"""
SupplierRepository
==================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.repositories.base import BaseRepository
from app.schemas.supplier import SupplierCreateSchema, SupplierUpdateSchema


class SupplierRepository(BaseRepository[Supplier, SupplierCreateSchema, SupplierUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Supplier)

    async def get_by_slug(self, slug: str, org_id: uuid.UUID) -> Optional[Supplier]:
        stmt = (
            select(Supplier)
            .where(
                Supplier.slug == slug,
                Supplier.org_id == org_id,
                Supplier.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(self, query: str, org_id: uuid.UUID) -> list[Supplier]:
        stmt = (
            select(Supplier)
            .where(
                Supplier.name.ilike(f"%{query}%"),
                Supplier.org_id == org_id,
                Supplier.deleted_at.is_(None),
            )
            .order_by(Supplier.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
