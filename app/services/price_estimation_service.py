"""
PriceEstimationService
======================
Orchestrates price estimation: stores results from AI pipelines,
manual entries, and supplier data.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.price_estimation_repository import PriceEstimationRepository
from app.schemas.price_estimation import (
    PriceEstimationCreateSchema,
    PriceEstimationUpdateSchema,
    PriceEstimationResponseSchema,
    PriceEstimationListItemSchema,
)
from app.services.base import BaseService


class PriceEstimationService(BaseService[PriceEstimationRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(PriceEstimationRepository(db))

    async def create_estimation(
        self, schema: PriceEstimationCreateSchema, org_id: uuid.UUID, owner_id: uuid.UUID
    ) -> PriceEstimationResponseSchema:
        data = {**schema.model_dump(), "org_id": org_id, "owner_id": owner_id}
        estimation = await self.repo.create_from_dict(data)
        return PriceEstimationResponseSchema.model_validate(estimation)

    async def get_estimation(
        self, estimation_id: uuid.UUID, org_id: uuid.UUID
    ) -> PriceEstimationResponseSchema:
        estimation = await self.get_by_id_or_fail(estimation_id, org_id, "PriceEstimation")
        return PriceEstimationResponseSchema.model_validate(estimation)

    async def list_estimations_for_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[PriceEstimationResponseSchema]:
        items = await self.repo.get_by_product(product_id, org_id)
        return [PriceEstimationResponseSchema.model_validate(e) for e in items]

    async def get_latest_for_product(
        self, product_id: uuid.UUID, org_id: uuid.UUID
    ) -> PriceEstimationResponseSchema | None:
        estimation = await self.repo.get_latest_for_product(product_id, org_id)
        if estimation is None:
            return None
        return PriceEstimationResponseSchema.model_validate(estimation)

    async def update_estimation(
        self,
        estimation_id: uuid.UUID,
        schema: PriceEstimationUpdateSchema,
        org_id: uuid.UUID,
    ) -> PriceEstimationResponseSchema:
        estimation = await self.get_by_id_or_fail(estimation_id, org_id, "PriceEstimation")
        updated = await self.repo.update(estimation, schema)
        return PriceEstimationResponseSchema.model_validate(updated)

    async def delete_estimation(self, estimation_id: uuid.UUID, org_id: uuid.UUID) -> None:
        await self.soft_delete_or_fail(estimation_id, org_id, "PriceEstimation")
