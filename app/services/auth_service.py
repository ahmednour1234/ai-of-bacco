"""
AuthService
===========
Handles login, token refresh, and logout with optional Redis token blacklisting.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException, ConflictException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.auth import TokenResponseSchema
from app.schemas.user import UserCreateSchema, UserResponseSchema
from app.utils.slugify import generate_slug

settings = get_settings()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def login(self, email: str, password: str) -> TokenResponseSchema:
        """
        Authenticate user credentials and return a JWT token pair.
        Equivalent to: Auth::attempt(['email' => $email, 'password' => $password])
        """
        user = await self.user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedException("Your account has been deactivated.")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return TokenResponseSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponseSchema:
        """
        Issue a new access token from a valid refresh token.
        """
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise UnauthorizedException("Invalid or expired refresh token.")

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Token is not a refresh token.")

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException("User not found or deactivated.")

        new_access_token = create_access_token(user.id)

        return TokenResponseSchema(
            access_token=new_access_token,
            refresh_token=refresh_token,  # reuse existing refresh token
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def register(
        self, schema: UserCreateSchema
    ) -> UserResponseSchema:
        """
        Register a new user + create a personal organization for them.
        Equivalent to: User::create([...]) in a RegisteredUserController.
        """
        if await self.user_repo.email_exists(schema.email):
            raise ConflictException("An account with this email already exists.")

        # Create a personal organization for the new user
        org_name = f"{schema.name}'s Organization"
        org_slug = generate_slug(org_name)
        org = await self.org_repo.create_from_dict({
            "name": org_name,
            "slug": org_slug,
            "is_active": True,
        })

        user = await self.user_repo.create_from_dict({
            "name": schema.name,
            "email": schema.email.lower(),
            "hashed_password": hash_password(schema.password),
            "is_active": True,
            "is_superuser": False,
            "org_id": org.id,
        })

        return UserResponseSchema.model_validate(user)
