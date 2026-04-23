"""
InvoiceItem Model
=================
Represents a single line item on an invoice.
May or may not be matched to a normalized Product.
"""

from __future__ import annotations
from typing import Optional

import uuid

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class InvoiceItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invoice_items"

    # ── FK ────────────────────────────────────────────────────────────────────
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Raw Data ──────────────────────────────────────────────────────────────
    raw_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(nullable=True)

    # ── Pricing ───────────────────────────────────────────────────────────────
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # ── Relationships ─────────────────────────────────────────────────────────
    invoice: Mapped["Invoice"] = relationship(  # noqa: F821
        "Invoice", back_populates="items", lazy="noload"
    )
    product: Mapped[Optional["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="invoice_items", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<InvoiceItem id={self.id} desc={self.raw_description!r} price={self.unit_price}>"
