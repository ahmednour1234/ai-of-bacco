"""
ExtractedItem Model
===================
Raw item extracted from a document by the AI pipeline, before normalization.
May be matched (linked) to a Product or left unmatched for manual review.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, TenantMixin


class ExtractedItem(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "extracted_items"

    # ── Source ────────────────────────────────────────────────────────────────
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Extracted Data ────────────────────────────────────────────────────────
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Matching ──────────────────────────────────────────────────────────────
    matched_product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ── Flexible Metadata ─────────────────────────────────────────────────────
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────────
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="extracted_items", lazy="noload"
    )
    matched_product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product", foreign_keys=[matched_product_id], lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<ExtractedItem id={self.id} matched={self.matched_product_id} score={self.confidence_score}>"
