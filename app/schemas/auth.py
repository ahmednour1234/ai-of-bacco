"""
Auth Schemas
============
Input/output schemas for authentication endpoints.
"""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, BaseResponseSchema


class LoginSchema(BaseSchema):
    """Equivalent to Laravel's LoginRequest."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class RefreshTokenSchema(BaseSchema):
    """Input schema for token refresh."""
    refresh_token: str


class TokenResponseSchema(BaseResponseSchema):
    """JWT token pair returned after successful login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
