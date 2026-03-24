"""
AIJob Model
===========
Tracks background AI processing jobs (OCR, extraction, estimation, embedding).
Equivalent to a job record in a database-driven queue table.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Payload & Result ──────────────────────────────────────────────────────
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    document: Mapped["Document | None"] = relationship(  # noqa: F821
        "Document", back_populates="ai_jobs", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AIJob id={self.id} type={self.job_type} status={self.status}>"
