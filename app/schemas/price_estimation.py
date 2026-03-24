"""
PriceEstimation Schemas
=======================
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, AliasChoices

from app.schemas.base import BaseSchema, BaseResponseSchema
from app.models.price_estimation import PriceSourceType


class PriceEstimationCreateSchema(BaseSchema):
    product_id: uuid.UUID
    estimated_price: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: PriceSourceType = PriceSourceType.AI_ESTIMATED
    valid_from: date | None = None
    valid_to: date | None = None
    metadata: dict[str, Any] | None = None


class PriceEstimationUpdateSchema(BaseSchema):
    estimated_price: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=3)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: PriceSourceType | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    metadata: dict[str, Any] | None = None


class PriceEstimationResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    estimated_price: float
    currency: str
    confidence: float | None
    source_type: PriceSourceType
    valid_from: date | None
    valid_to: date | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices('extra_metadata', 'metadata'))
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PriceEstimationListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    estimated_price: float
    currency: str
    source_type: PriceSourceType
    confidence: float | None
    valid_from: date | None
    created_at: datetime
