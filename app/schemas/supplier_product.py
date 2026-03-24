"""
SupplierProduct Schemas
=======================
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class SupplierProductCreateSchema(BaseSchema):
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    supplier_sku: str | None = None
    price: float | None = None
    currency: str = Field(default="USD", max_length=3)
    effective_date: date | None = None


class SupplierProductUpdateSchema(BaseSchema):
    supplier_sku: str | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=3)
    effective_date: date | None = None
    is_active: bool | None = None


class SupplierProductResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    supplier_sku: str | None
    price: float | None
    currency: str
    effective_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
