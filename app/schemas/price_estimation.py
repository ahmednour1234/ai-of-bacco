"""
PriceEstimation Schemas
=======================
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional, Any

from pydantic import Field, AliasChoices

from app.schemas.base import BaseSchema, BaseResponseSchema
from app.models.price_estimation import PriceSourceType


class PriceEstimationCreateSchema(BaseSchema):
    product_id: uuid.UUID
    estimated_price: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_type: PriceSourceType = PriceSourceType.AI_ESTIMATED
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    metadata: Optional[dict[str, Any]] = None


class PriceEstimationUpdateSchema(BaseSchema):
    estimated_price: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, max_length=3)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_type: Optional[PriceSourceType] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    metadata: Optional[dict[str, Any]] = None


class PriceEstimationResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    estimated_price: float
    currency: str
    confidence: Optional[float]
    source_type: PriceSourceType
    valid_from: Optional[date]
    valid_to: Optional[date]
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias=AliasChoices('extra_metadata', 'metadata'))
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PriceEstimationListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    estimated_price: float
    currency: str
    source_type: PriceSourceType
    confidence: Optional[float]
    valid_from: Optional[date]
    created_at: datetime
