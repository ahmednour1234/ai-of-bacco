"""
ExtractionSession Model
=======================
Tracks a single file-upload extraction job.

One session is created per uploaded file.  It owns all ExtractionCandidate rows
produced by the extraction pipeline.  The status field drives the review UI:
    pending   → extraction finished, no review started
    reviewing → user opened the review view
    completed → user has submitted feedback for all candidates
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ExtractionSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "extraction_sessions"

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # pending | reviewing | completed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )

    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Raw extracted text stored for debugging / re-run
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Universal pipeline detection results ──────────────────────────────────
    contains_products: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    document_type_guess: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detection_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Stores raw LLM responses / heuristic scores for auditability + fine-tuning
    detection_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    candidates: Mapped[list["ExtractionCandidate"]] = relationship(  # noqa: F821
        "ExtractionCandidate",
        back_populates="session",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="ExtractionCandidate.position",
    )

    def __repr__(self) -> str:
        return (
            f"<ExtractionSession id={self.id} "
            f"file={self.filename!r} status={self.status}>"
        )
