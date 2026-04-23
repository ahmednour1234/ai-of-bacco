"""
BaseService
===========
Generic business logic base class.
Equivalent to a Laravel base Service wrapping a Repository.

All services extend this class. The repository is injected via the constructor,
following the same Dependency Injection pattern Laravel uses with its service container.

Type parameter:
    RepositoryType — the repository class this service wraps
"""

from __future__ import annotations

import uuid
from typing import Optional, Any, Generic, TypeVar

from app.core.exceptions import NotFoundException
from app.repositories.base import BaseRepository

RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[RepositoryType]):
    """
    Generic service base providing common operations backed by a repository.
    Equivalent to a Laravel Service class with injected Repository.
    """

    def __init__(self, repo: RepositoryType) -> None:
        self.repo = repo

    async def get_by_id_or_fail(
        self,
        record_id: uuid.UUID | str,
        org_id: Optional[uuid.UUID] = None,
        resource_name: str = "Resource",
    ):
        """
        Retrieve a record by ID or raise NotFoundException.
        Equivalent to: Model::findOrFail($id) in Laravel.
        """
        instance = await self.repo.get_by_id(record_id, org_id)
        if instance is None:
            raise NotFoundException(f"{resource_name} with id '{record_id}' not found.")
        return instance

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 15,
        org_id: Optional[uuid.UUID] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> tuple[list, int]:
        """Paginate records. Returns (items, total)."""
        return await self.repo.paginate(
            page=page,
            per_page=per_page,
            org_id=org_id,
            filters=filters,
        )

    async def soft_delete_or_fail(
        self,
        record_id: uuid.UUID | str,
        org_id: Optional[uuid.UUID] = None,
        resource_name: str = "Resource",
    ) -> None:
        """Find and soft-delete a record, raising NotFoundException if missing."""
        instance = await self.get_by_id_or_fail(record_id, org_id, resource_name)
        await self.repo.soft_delete(instance)
