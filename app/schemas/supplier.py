"""
Supplier Schemas
================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import EmailStr, Field, AliasChoices

from app.schemas.base import BaseSchema, BaseResponseSchema


class SupplierCreateSchema(BaseSchema):
    name: str = Field(..., min_length=1, max_length=512)
    contact_email: Optional[EmailStr] = None
    website: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SupplierUpdateSchema(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    contact_email: Optional[EmailStr] = None
    website: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SupplierResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    slug: str
    contact_email: Optional[str]
    website: Optional[str]
    country: Optional[str]
    description: Optional[str]
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias=AliasChoices('extra_metadata', 'metadata'))
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SupplierListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    slug: str
    country: Optional[str]
    created_at: datetime
