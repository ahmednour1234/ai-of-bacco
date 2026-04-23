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
    document_id: Optional[uuid.UUID] = None
    supplier_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = Field(default=None, max_length=128)
    invoice_date: Optional[date] = None
    total_amount: Optional[float] = None
    currency: str = Field(default="USD", max_length=3)


class InvoiceUpdateSchema(BaseSchema):
    supplier_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = Field(default=None, max_length=128)
    invoice_date: Optional[date] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=3)


class InvoiceResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    document_id: Optional[uuid.UUID]
    supplier_id: Optional[uuid.UUID]
    invoice_number: Optional[str]
    invoice_date: Optional[date]
    total_amount: Optional[float]
    currency: str
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class InvoiceListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    invoice_number: Optional[str]
    invoice_date: Optional[date]
    total_amount: Optional[float]
    currency: str
    created_at: datetime
