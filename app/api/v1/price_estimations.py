"""
app/api/v1/price_estimations.py
---------------------------------
Price estimation CRUD endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserDep, DbDep
from app.core.response import created_response, no_content_response, paginated_response, success_response
from app.schemas.price_estimation import PriceEstimationCreateSchema, PriceEstimationUpdateSchema
from app.services.price_estimation_service import PriceEstimationService

router = APIRouter(prefix="/price-estimations", tags=["Price Estimations"])


@router.get("/")
async def list_estimations(
    db: DbDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    product_id: Optional[uuid.UUID] = Query(None, description="Filter by product"),
):
    service = PriceEstimationService(db)
    if product_id:
        items, total = await service.list_estimations_for_product(
            product_id=product_id, org_id=current_user.org_id, page=page, per_page=per_page
        )
    else:
        items, total = await service.list_paginated(
            page=page, per_page=per_page, org_id=current_user.org_id
        )
        from app.schemas.price_estimation import PriceEstimationListItemSchema
        items = [PriceEstimationListItemSchema.model_validate(i) for i in items]
    return paginated_response(items=items, total=total, page=page, per_page=per_page)


@router.post("/", status_code=201)
async def create_estimation(
    schema: PriceEstimationCreateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    service = PriceEstimationService(db)
    estimation = await service.create_estimation(
        schema=schema, org_id=current_user.org_id, owner_id=current_user.id
    )
    return created_response(data=estimation, message="Price estimation created.")


@router.get("/{estimation_id}")
async def get_estimation(estimation_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = PriceEstimationService(db)
    estimation = await service.get_estimation(estimation_id, org_id=current_user.org_id)
    return success_response(data=estimation)


@router.patch("/{estimation_id}")
async def update_estimation(
    estimation_id: uuid.UUID,
    schema: PriceEstimationUpdateSchema,
    db: DbDep,
    current_user: CurrentUserDep,
):
    service = PriceEstimationService(db)
    estimation = await service.update_estimation(estimation_id, schema, org_id=current_user.org_id)
    return success_response(data=estimation, message="Estimation updated.")


@router.delete("/{estimation_id}", status_code=204)
async def delete_estimation(estimation_id: uuid.UUID, db: DbDep, current_user: CurrentUserDep):
    service = PriceEstimationService(db)
    await service.delete_estimation(estimation_id, org_id=current_user.org_id)
    return no_content_response()
