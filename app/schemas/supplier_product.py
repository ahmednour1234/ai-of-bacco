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
    supplier_sku: Optional[str] = None
    price: Optional[float] = None
    currency: str = Field(default="USD", max_length=3)
    effective_date: Optional[date] = None


class SupplierProductUpdateSchema(BaseSchema):
    supplier_sku: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=3)
    effective_date: Optional[date] = None
    is_active: Optional[bool] = None


class SupplierProductResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    supplier_sku: Optional[str]
    price: Optional[float]
    currency: str
    effective_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime
