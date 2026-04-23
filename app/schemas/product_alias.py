"""
ProductAlias Schemas
====================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class ProductAliasCreateSchema(BaseSchema):
    product_id: uuid.UUID
    alias_text: str = Field(..., min_length=1)
    source: Optional[str] = None
    language: Optional[str] = "en"


class ProductAliasResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    product_id: uuid.UUID
    alias_text: str
    source: Optional[str]
    language: Optional[str]
    created_at: datetime
