"""
SupplierProductRepository
=========================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier_product import SupplierProduct
from app.repositories.base import BaseRepository
from app.schemas.supplier_product import SupplierProductCreateSchema, SupplierProductUpdateSchema


class SupplierProductRepository(BaseRepository[SupplierProduct, SupplierProductCreateSchema, SupplierProductUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, SupplierProduct)

    async def get_by_supplier(
        self, supplier_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[SupplierProduct]:
        stmt = (
            select(SupplierProduct)
            .where(
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.org_id == org_id,
            )
            .order_by(SupplierProduct.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[SupplierProduct]:
        stmt = (
            select(SupplierProduct)
            .where(
                SupplierProduct.product_id == product_id,
                SupplierProduct.org_id == org_id,
            )
            .order_by(SupplierProduct.effective_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_price(
        self, supplier_id: uuid.UUID, product_id: uuid.UUID
    ) -> Optional[SupplierProduct]:
        """Get the active supplier-product price entry."""
        stmt = (
            select(SupplierProduct)
            .where(
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.product_id == product_id,
                SupplierProduct.is_active.is_(True),
            )
            .order_by(SupplierProduct.effective_date.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
