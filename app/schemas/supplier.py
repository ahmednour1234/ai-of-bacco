"""
Supplier Schemas
================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, AliasChoices

from app.schemas.base import BaseSchema, BaseResponseSchema


class SupplierCreateSchema(BaseSchema):
    name: str = Field(..., min_length=1, max_length=512)
    contact_email: EmailStr | None = None
    website: str | None = None
    country: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class SupplierUpdateSchema(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    contact_email: EmailStr | None = None
    website: str | None = None
    country: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class SupplierResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    slug: str
    contact_email: str | None
    website: str | None
    country: str | None
    description: str | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices('extra_metadata', 'metadata'))
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SupplierListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    slug: str
    country: str | None
    created_at: datetime
