"""
SQLAlchemy Model Mixins (Traits)
================================
Equivalent to Laravel's model traits (HasTimestamps, SoftDeletes, etc.)

Four reusable mixins that are composed into each model:
    - UUIDMixin         → UUID primary key (like $primaryKey = 'id' with UUID cast)
    - TimestampMixin    → created_at / updated_at (like HasTimestamps)
    - SoftDeleteMixin   → deleted_at / is_deleted (like SoftDeletes)
    - TenantMixin       → org_id / owner_id scoping (multi-tenancy)

Usage:
    class Product(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
        __tablename__ = "products"
        ...
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """
    Provides a UUID primary key column.
    Equivalent to using $incrementing = false; protected $keyType = 'string'; in Laravel.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        index=True,
    )


class TimestampMixin:
    """
    Provides created_at and updated_at columns.
    Equivalent to Laravel's HasTimestamps trait / $timestamps = true.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """
    Provides soft-delete functionality via a deleted_at timestamp.
    Equivalent to Laravel's SoftDeletes trait.

    To filter active (non-deleted) records, add:
        .where(Model.deleted_at.is_(None))
    or use BaseRepository which handles this automatically.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if this record has been soft-deleted. Like $model->trashed()."""
        return self.deleted_at is not None


class TenantMixin:
    """
    Provides multi-tenant scoping via org_id and owner_id.
    Equivalent to a global scope in Laravel that filters by organization.

    Every query in BaseRepository applies a WHERE org_id = :tenant_id filter
    automatically when a tenant_id is provided.
    """

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
