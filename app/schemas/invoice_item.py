"""
InvoiceItem Schemas
===================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class InvoiceItemCreateSchema(BaseSchema):
    invoice_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    raw_description: Optional[str] = None
    line_number: Optional[int] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = Field(default="USD", max_length=3)


class InvoiceItemUpdateSchema(BaseSchema):
    product_id: Optional[uuid.UUID] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class InvoiceItemResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    invoice_id: uuid.UUID
    product_id: Optional[uuid.UUID]
    raw_description: Optional[str]
    line_number: Optional[int]
    quantity: Optional[float]
    unit: Optional[str]
    unit_price: Optional[float]
    total_price: Optional[float]
    currency: str
    created_at: datetime
