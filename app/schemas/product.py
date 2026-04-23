"""
Product Schemas
===============
Equivalent to Laravel Form Requests (input) + API Resources (output).

Four schemas per entity — a pattern to follow for all modules:
    ProductCreateSchema     → POST  /products       (FormRequest equivalent)
    ProductUpdateSchema     → PATCH /products/{id}  (FormRequest equivalent)
    ProductResponseSchema   → single item response  (API Resource equivalent)
    ProductListItemSchema   → list view (slimmed)   (API Resource collection)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import Field, field_validator, AliasChoices

from app.schemas.base import BaseSchema, BaseResponseSchema


# ── Input Schemas (Form Requests) ─────────────────────────────────────────────

class ProductCreateSchema(BaseSchema):
    """
    Validated input for creating a new product.
    Equivalent to Laravel's StoreProductRequest.
    """
    name: str = Field(..., min_length=1, max_length=512, examples=["Stainless Steel Bolt M8"])
    sku: Optional[str] = Field(default=None, max_length=128, examples=["BOLT-M8-SS"])
    category: Optional[str] = Field(default=None, max_length=255, examples=["Fasteners"])
    unit: Optional[str] = Field(default=None, max_length=64, examples=["pcs"])
    description: Optional[str] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Product name cannot be blank.")
        return v.strip()


class ProductUpdateSchema(BaseSchema):
    """
    Validated input for updating a product (all fields optional — PATCH semantics).
    Equivalent to Laravel's UpdateProductRequest.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    sku: Optional[str] = Field(default=None, max_length=128)
    category: Optional[str] = Field(default=None, max_length=255)
    unit: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)


# ── Output Schemas (API Resources) ────────────────────────────────────────────

class ProductResponseSchema(BaseResponseSchema):
    """
    Full product representation returned from the API.
    Equivalent to Laravel's ProductResource.
    """
    id: uuid.UUID
    name: str
    slug: str
    sku: Optional[str]
    category: Optional[str]
    unit: Optional[str]
    description: Optional[str]
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias=AliasChoices('extra_metadata', 'metadata'))
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProductListItemSchema(BaseResponseSchema):
    """
    Slimmed-down product representation for list views.
    Equivalent to Laravel's ProductResource in a collection context.
    """
    id: uuid.UUID
    name: str
    slug: str
    sku: Optional[str]
    category: Optional[str]
    unit: Optional[str]
    created_at: datetime
