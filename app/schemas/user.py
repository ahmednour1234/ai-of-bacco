"""
User Schemas
============
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class UserCreateSchema(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    org_id: Optional[uuid.UUID] = None


class UserUpdateSchema(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None


class UserResponseSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    is_superuser: bool
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UserListItemSchema(BaseResponseSchema):
    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime
