"""
Supplier Model
==============
Represents a product supplier / vendor.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Supplier(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────────
    supplier_products: Mapped[list["SupplierProduct"]] = relationship(  # noqa: F821
        "SupplierProduct", back_populates="supplier", lazy="noload"
    )
    invoices: Mapped[list["Invoice"]] = relationship(  # noqa: F821
        "Invoice", back_populates="supplier", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} name={self.name!r}>"
