"""
UserService
===========
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserListItemSchema
from app.services.base import BaseService


class UserService(BaseService[UserRepository]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserRepository(db))

    async def get_user(self, user_id: uuid.UUID, org_id: uuid.UUID) -> UserResponseSchema:
        user = await self.get_by_id_or_fail(user_id, org_id, "User")
        return UserResponseSchema.model_validate(user)

    async def list_users(
        self, org_id: uuid.UUID, page: int = 1, per_page: int = 15
    ) -> tuple[list[UserListItemSchema], int]:
        items, total = await self.list_paginated(page=page, per_page=per_page, org_id=org_id)
        return [UserListItemSchema.model_validate(u) for u in items], total

    async def update_user(
        self, user_id: uuid.UUID, schema: UserUpdateSchema, org_id: uuid.UUID
    ) -> UserResponseSchema:
        user = await self.get_by_id_or_fail(user_id, org_id, "User")
        if schema.email and schema.email != user.email:
            if await self.repo.email_exists(schema.email):
                raise ConflictException("Email is already in use.")
        updated = await self.repo.update(user, schema)
        return UserResponseSchema.model_validate(updated)

    async def delete_user(self, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        await self.soft_delete_or_fail(user_id, org_id, "User")
