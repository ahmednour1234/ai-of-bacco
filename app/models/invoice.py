"""
Invoice Model
=============
Represents a parsed invoice document with header information.
Line items are stored in InvoiceItem.
"""

from __future__ import annotations
from typing import Optional

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin


class Invoice(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "invoices"

    # ── Source ────────────────────────────────────────────────────────────────
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Invoice Header ────────────────────────────────────────────────────────
    invoice_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # ── Relationships ─────────────────────────────────────────────────────────
    document: Mapped[Optional["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="invoice", lazy="noload"
    )
    supplier: Mapped[Optional["Supplier"]] = relationship(  # noqa: F821
        "Supplier", back_populates="invoices", lazy="noload"
    )
    items: Mapped[list["InvoiceItem"]] = relationship(  # noqa: F821
        "InvoiceItem", back_populates="invoice", lazy="noload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r}>"
