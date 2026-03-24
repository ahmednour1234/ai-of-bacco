"""
Invoice Schemas
===============
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class InvoiceCreateSchema(BaseSchema):
    document_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    invoice_number: str | None = Field(default=None, max_length=128)
    invoice_date: date | None = None
    total_amount: float | None = None
    currency: str = Field(default="USD", max_length=3)


class InvoiceUpdateSchema(BaseSchema):
    supplier_id: uuid.UUID | None = None
    invoice_number: str | None = Field(default=None, max_length=128)
    invoice_date: date | None = None
    total_amount: float | None = None
    currency: str | None = Field(default=None, max_length=3)


class InvoiceResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    document_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    invoice_number: str | None
    invoice_date: date | None
    total_amount: float | None
    currency: str
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class InvoiceListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    invoice_number: str | None
    invoice_date: date | None
    total_amount: float | None
    currency: str
    created_at: datetime
