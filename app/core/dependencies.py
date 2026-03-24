"""
FastAPI Dependencies
====================
Equivalent to Laravel's middleware + service container bindings.

Provides reusable Depends() callables injected into route functions.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.storage.base import StorageDriver

# Re-export get_db so callers only need to import from dependencies
__all__ = [
    "get_db",
    "get_request_user",
    "get_storage_driver",
    "DbDep",
    "CurrentUserDep",
]


async def _get_or_create_public_user(db: AsyncSession) -> User:
    """Return a reusable default user when API auth is disabled."""
    stmt = (
        select(User)
        .where(User.deleted_at.is_(None), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        return existing_user

    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    organization = await org_repo.get_by_slug("public-organization")
    if organization is None:
        organization = await org_repo.create_from_dict({
            "name": "Public Organization",
            "slug": "public-organization",
            "description": "Auto-created organization for unauthenticated API access.",
            "is_active": True,
        })

    public_user = await user_repo.get_by_email("public@qumta.local")
    if public_user is None:
        public_user = await user_repo.create_from_dict({
            "name": "Public API User",
            "email": "public@qumta.local",
            "hashed_password": hash_password("public-access"),
            "is_active": True,
            "is_superuser": True,
            "org_id": organization.id,
        })

    return public_user


async def get_request_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the default request user for public APIs with no auth middleware."""
    return await _get_or_create_public_user(db)


def get_storage_driver() -> StorageDriver:
    """
    Return the configured storage driver (local or S3).
    Equivalent to Laravel's Storage::disk() façade factory.
    """
    from app.core.config import get_settings
    from app.storage.local_driver import LocalStorageDriver
    from app.storage.s3_driver import S3StorageDriver

    settings = get_settings()
    if settings.STORAGE_DRIVER == "s3":
        return S3StorageDriver()
    return LocalStorageDriver()


# ── Annotated type aliases (Laravel-style shorthand) ─────────────────────────
# Usage: async def endpoint(db: DbDep, user: CurrentUserDep): ...
DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_request_user)]
