"""
AIJob Model
===========
Tracks background AI processing jobs (OCR, extraction, estimation, embedding).
Equivalent to a job record in a database-driven queue table.
"""

from __future__ import annotations
from typing import Optional

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, TenantMixin


class AIJobType(str, enum.Enum):
    OCR = "ocr"
    PDF_PARSE = "pdf_parse"
    IMAGE_PARSE = "image_parse"
    PRODUCT_EXTRACTION = "product_extraction"
    PRICE_ESTIMATION = "price_estimation"
    EMBEDDING = "embedding"
    WEB_SCRAPE = "web_scrape"


class AIJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJob(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "ai_jobs"

    # ── Classification ────────────────────────────────────────────────────────
    job_type: Mapped[AIJobType] = mapped_column(
        Enum(AIJobType, name="ai_job_type_enum"),
        nullable=False,
        index=True,
    )
    status: Mapped[AIJobStatus] = mapped_column(
        Enum(AIJobStatus, name="ai_job_status_enum"),
        nullable=False,
        default=AIJobStatus.PENDING,
        index=True,
    )

    # ── Context ───────────────────────────────────────────────────────────────
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Payload & Result ──────────────────────────────────────────────────────
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    document: Mapped[Optional["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="ai_jobs", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AIJob id={self.id} type={self.job_type} status={self.status}>"
