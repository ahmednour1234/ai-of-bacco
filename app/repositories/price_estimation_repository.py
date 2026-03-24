"""
PriceEstimationRepository
=========================
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_estimation import PriceEstimation, PriceSourceType
from app.repositories.base import BaseRepository
from app.schemas.price_estimation import PriceEstimationCreateSchema, PriceEstimationUpdateSchema


class PriceEstimationRepository(BaseRepository[PriceEstimation, PriceEstimationCreateSchema, PriceEstimationUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, PriceEstimation)

    async def get_by_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[PriceEstimation]:
        stmt = (
            select(PriceEstimation)
            .where(
                PriceEstimation.product_id == product_id,
                PriceEstimation.org_id == org_id,
            )
            .order_by(PriceEstimation.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> PriceEstimation | None:
        """Get the most recent price estimation for a product."""
        stmt = (
            select(PriceEstimation)
            .where(
                PriceEstimation.product_id == product_id,
                PriceEstimation.org_id == org_id,
            )
            .order_by(PriceEstimation.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_source_type(
        self, source_type: PriceSourceType, org_id: uuid.UUID
    ) -> list[PriceEstimation]:
        stmt = (
            select(PriceEstimation)
            .where(
                PriceEstimation.source_type == source_type,
                PriceEstimation.org_id == org_id,
            )
            .order_by(PriceEstimation.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
