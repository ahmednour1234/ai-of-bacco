"""
UserRepository
==============
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreateSchema, UserUpdateSchema


class UserRepository(BaseRepository[User, UserCreateSchema, UserUpdateSchema]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email address (global — no tenant filter)."""
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check whether an email is already registered."""
        return await self.get_by_email(email) is not None
