"""
ExtractionFeedbackEvent Model
==============================
Immutable audit log of every human correction applied to an ExtractionCandidate.

One row is inserted each time a FeedbackItemSchema is processed.
Never deleted or updated — used for retraining data, audit trails, and analytics.

Fields:
    candidate_id  → FK to extraction_candidates.id
    session_id    → FK to extraction_sessions.id (denormalised for query speed)
    user_id       → FK to users.id (nullable — system corrections have no user)
    event_type    → approve | reject | correct
    changed_fields → list of field names that were changed (JSONB array)
    old_values     → snapshot of values BEFORE correction (JSONB object)
    new_values     → snapshot of values AFTER correction (JSONB object)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class ExtractionFeedbackEvent(UUIDMixin, Base):
    __tablename__ = "extraction_feedback_events"

    # ── Foreign keys ───────────────────────────────────────────────────────────
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Event metadata ─────────────────────────────────────────────────────────
    # approve | reject | correct
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Text note from the reviewer (optional)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Change payload ─────────────────────────────────────────────────────────
    # ["product_name", "quantity", "unit", …]
    changed_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Snapshot of the candidate values BEFORE the correction was applied
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Snapshot of the new / corrected values
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    # Separate from UUIDMixin (no TimestampMixin — immutable rows, created_at only)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
