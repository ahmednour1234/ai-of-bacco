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
    product_id: uuid.UUID | None = None
    raw_description: str | None = None
    line_number: int | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None
    currency: str = Field(default="USD", max_length=3)


class InvoiceItemUpdateSchema(BaseSchema):
    product_id: uuid.UUID | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total_price: float | None = None


class InvoiceItemResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    invoice_id: uuid.UUID
    product_id: uuid.UUID | None
    raw_description: str | None
    line_number: int | None
    quantity: float | None
    unit: str | None
    unit_price: float | None
    total_price: float | None
    currency: str
    created_at: datetime
