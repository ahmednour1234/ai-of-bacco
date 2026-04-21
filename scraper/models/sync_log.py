"""
scraper/models/sync_log.py
---------------------------
Audit trail for every sync attempt made by SyncService.

Every POST to the external API (success or failure) is recorded here,
making the sync pipeline fully database-driven and auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scraper.core.database import ScraperBase
from scraper.models.base import ScraperTimestampMixin


class ScraperSyncLog(ScraperTimestampMixin, ScraperBase):
    __tablename__ = "scraper_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scraper_product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scraper_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Sync result ────────────────────────────────────────────────────────────
    sync_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "success" | "failed"
    request_payload: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # serialised JSON sent to the external API
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    product: Mapped["ScraperProduct"] = relationship(  # noqa: F821
        back_populates="sync_logs", lazy="noload"
    )
