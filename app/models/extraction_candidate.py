"""
ExtractionCandidate Model
=========================
Represents one predicted row / line from an ExtractionSession.

Stores both the machine-generated prediction (predicted_label, confidence,
product_name, …) and the human correction (corrected_label, corrected_name, …)
in a single row so the diff is immediately visible.

Status lifecycle:
    pending   → created by extraction pipeline, awaiting user review
    approved  → user confirmed prediction is correct
    rejected  → user flagged as wrong / irrelevant
    corrected → user submitted an edited version
"""

from __future__ import annotations
from typing import Optional

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ExtractionCandidate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "extraction_candidates"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Zero-based position in original document — preserves reading order
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Raw input ──────────────────────────────────────────────────────────────
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Machine prediction ─────────────────────────────────────────────────────
    # product | description | meta | total | ignore | price_row | header
    predicted_label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    product_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # True when confidence < threshold or the line is ambiguous
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Universal pipeline provenance ──────────────────────────────────────────
    # Which document region this candidate came from
    region_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    region_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Bounding box: {x0, y0, x1, y1, page} in document coordinates
    coordinates: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # "llm" | "heuristic"
    classification_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── Human correction ───────────────────────────────────────────────────────
    # pending | approved | rejected | corrected
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )

    corrected_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    corrected_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    corrected_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corrected_unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    corrected_brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    corrected_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    corrected_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    correction_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationship ───────────────────────────────────────────────────────────
    session: Mapped["ExtractionSession"] = relationship(  # noqa: F821
        "ExtractionSession", back_populates="candidates"
    )

    # ── Computed effective values (correction wins over prediction) ────────────

    @property
    def effective_label(self) -> str:
        return self.corrected_label or self.predicted_label

    @property
    def effective_name(self) -> str | None:
        return self.corrected_name or self.product_name

    @property
    def effective_category(self) -> str | None:
        return self.corrected_category or self.category

    @property
    def effective_brand(self) -> str | None:
        return self.corrected_brand or self.brand

    @property
    def effective_quantity(self) -> float | None:
        if self.corrected_quantity is not None:
            return self.corrected_quantity
        return self.quantity

    @property
    def effective_unit(self) -> str | None:
        return self.corrected_unit or self.unit

    @property
    def effective_price(self) -> float | None:
        if self.corrected_price is not None:
            return self.corrected_price
        return self.price

    @property
    def effective_description(self) -> str | None:
        return self.corrected_description or self.description

    def __repr__(self) -> str:
        return (
            f"<ExtractionCandidate id={self.id} "
            f"label={self.predicted_label} name={self.product_name!r}>"
        )
