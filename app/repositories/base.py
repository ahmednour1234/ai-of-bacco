"""
BaseRepository
==============
Generic data-access layer base class.
Equivalent to a Laravel Repository base implementing a RepositoryInterface.

All repositories extend this class and inherit full CRUD + pagination.
Tenant scoping is enforced automatically when org_id is provided.

Type parameters:
    ModelType   — the SQLAlchemy model class
    CreateSchema — the Pydantic create schema
    UpdateSchema — the Pydantic update schema (all-optional)

Usage:
    class ProductRepository(BaseRepository[Product, ProductCreateSchema, ProductUpdateSchema]):
        def __init__(self, db: AsyncSession) -> None:
            super().__init__(db, Product)
"""

from __future__ import annotations

import uuid
from typing import Optional, Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")


class BaseRepository(Generic[ModelType, CreateSchema, UpdateSchema]):
    """
    Generic repository providing CRUD + pagination for any SQLAlchemy model.
    Equivalent to a Laravel base Repository with Eloquent under the hood.
    """

    def __init__(self, db: AsyncSession, model: type[ModelType]) -> None:
        self.db = db
        self.model = model

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(
        self,
        record_id: uuid.UUID | str,
        org_id: Optional[uuid.UUID] = None,
    ) -> Optional[ModelType]:
        """
        Find by primary key.
        Equivalent to: Model::find($id) or Model::where('org_id', $org)->find($id)
        """
        stmt = select(self.model).where(
            self.model.id == record_id,  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        if org_id is not None:
            stmt = stmt.where(self.model.org_id == org_id)  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        org_id: Optional[uuid.UUID] = None,
        filters: Optional[dict[str, Any]] = None,
        order_by: Any = None,
    ) -> list[ModelType]:
        """
        Return all matching records.
        Equivalent to: Model::where('org_id', $org)->get()
        """
        stmt = select(self.model)
        stmt = self._apply_soft_delete_filter(stmt)
        if org_id is not None:
            stmt = stmt.where(self.model.org_id == org_id)  # type: ignore[attr-defined]
        if filters:
            stmt = self._apply_filters(stmt, filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def paginate(
        self,
        page: int = 1,
        per_page: int = 15,
        org_id: Optional[uuid.UUID] = None,
        filters: Optional[dict[str, Any]] = None,
        order_by: Any = None,
    ) -> tuple[list[ModelType], int]:
        """
        Paginate results. Returns (items, total_count).
        Equivalent to: Model::paginate($perPage)
        """
        offset = (page - 1) * per_page

        # Base stmt for data
        stmt = select(self.model)
        stmt = self._apply_soft_delete_filter(stmt)
        if org_id is not None:
            stmt = stmt.where(self.model.org_id == org_id)  # type: ignore[attr-defined]
        if filters:
            stmt = self._apply_filters(stmt, filters)

        # Count stmt (before ordering/limiting)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Data stmt
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(per_page)
        data_result = await self.db.execute(stmt)
        items = list(data_result.scalars().all())

        return items, total

    async def exists(
        self,
        record_id: uuid.UUID | str,
        org_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check if a record exists. Equivalent to: Model::where(...)->exists()"""
        stmt = select(func.count()).where(
            self.model.id == record_id  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        if org_id is not None:
            stmt = stmt.where(self.model.org_id == org_id)  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        return (result.scalar_one() or 0) > 0

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, schema: CreateSchema) -> ModelType:
        """
        Create a record from a Pydantic schema.
        Equivalent to: Model::create($data)
        """
        data = schema.model_dump(exclude_unset=False)  # type: ignore[union-attr]
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def create_from_dict(self, data: dict[str, Any]) -> ModelType:
        """Create directly from a plain dict (useful in services)."""
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(
        self,
        instance: ModelType,
        schema: UpdateSchema,
    ) -> ModelType:
        """
        Apply a partial-update schema to an existing model instance.
        Equivalent to: $model->update($data) with only set fields.
        """
        data = schema.model_dump(exclude_unset=True)  # type: ignore[union-attr]
        for field, value in data.items():
            setattr(instance, field, value)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update_fields(
        self,
        instance: ModelType,
        **kwargs: Any,
    ) -> ModelType:
        """Update individual fields by keyword argument."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelType) -> ModelType:
        """
        Soft-delete: sets deleted_at timestamp.
        Equivalent to: $model->delete() when SoftDeletes is used.
        """
        from datetime import datetime, timezone
        instance.deleted_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def hard_delete(self, instance: ModelType) -> None:
        """
        Permanently delete a record.
        Equivalent to: $model->forceDelete()
        """
        await self.db.delete(instance)
        await self.db.flush()

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """Automatically exclude soft-deleted rows if model uses SoftDeleteMixin."""
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    def _apply_filters(self, stmt: Any, filters: dict[str, Any]) -> Any:
        """
        Apply simple equality filters from a dict.
        For complex queries, override in the child repository.
        """
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                stmt = stmt.where(getattr(self.model, field) == value)
        return stmt
