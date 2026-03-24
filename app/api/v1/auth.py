"""
app/api/v1/auth.py
-------------------
Authentication endpoints: login, refresh, register.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DbDep
from app.core.response import created_response, success_response
from app.schemas.auth import LoginSchema, RefreshTokenSchema
from app.schemas.user import UserCreateSchema
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(schema: LoginSchema, db: DbDep):
    """Authenticate a user and return access + refresh tokens."""
    service = AuthService(db)
    tokens = await service.login(schema)
    return success_response(data=tokens, message="Login successful.")


@router.post("/refresh")
async def refresh(schema: RefreshTokenSchema, db: DbDep):
    """Issue a new access token using a valid refresh token."""
    service = AuthService(db)
    tokens = await service.refresh(schema)
    return success_response(data=tokens, message="Token refreshed.")


@router.post("/register", status_code=201)
async def register(schema: UserCreateSchema, db: DbDep):
    """Create a new organization and admin user."""
    service = AuthService(db)
    user = await service.register(schema)
    return created_response(data=user, message="Registration successful.")
