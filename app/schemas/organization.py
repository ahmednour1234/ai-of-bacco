"""
Organization Schemas
====================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class OrganizationCreateSchema(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class OrganizationUpdateSchema(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
