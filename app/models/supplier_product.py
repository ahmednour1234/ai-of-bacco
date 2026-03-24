"""
SupplierProduct Model
=====================
Junction table linking a Supplier to a Product, with supplier-specific pricing.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, TenantMixin


class SupplierProduct(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "supplier_products"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    supplier: Mapped["Supplier"] = relationship(  # noqa: F821
        "Supplier", back_populates="supplier_products", lazy="noload"
    )
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="supplier_products", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<SupplierProduct supplier={self.supplier_id} product={self.product_id} price={self.price}>"
