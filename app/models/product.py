"""
Product Model
=============
Central entity. Represents a normalized, deduplicated product record.
Equivalent to a Laravel Eloquent Product model.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Product(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "products"

    # ── Identity ──────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    sku: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # ── Classification ────────────────────────────────────────────────────────
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # e.g. "kg", "pcs", "box"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Flexible Metadata ─────────────────────────────────────────────────────
    # Store extra structured data (brand, dimensions, etc.) without schema changes.
    # Equivalent to Laravel JSON cast: protected $casts = ['metadata' => 'array']
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────────
    aliases: Mapped[list["ProductAlias"]] = relationship(  # noqa: F821
        "ProductAlias", back_populates="product", lazy="noload", cascade="all, delete-orphan"
    )
    supplier_products: Mapped[list["SupplierProduct"]] = relationship(  # noqa: F821
        "SupplierProduct", back_populates="product", lazy="noload"
    )
    invoice_items: Mapped[list["InvoiceItem"]] = relationship(  # noqa: F821
        "InvoiceItem", back_populates="product", lazy="noload"
    )
    price_estimations: Mapped[list["PriceEstimation"]] = relationship(  # noqa: F821
        "PriceEstimation", back_populates="product", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} sku={self.sku!r}>"
