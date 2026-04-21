"""
scraper/models/base.py
-----------------------
Shared timestamp mixin for all scraper models.
Mirrors TimestampMixin from app.models.base but is kept separate to
avoid any coupling with the main application's model layer.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class ScraperTimestampMixin:
    """Provides created_at and updated_at columns for every scraper model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
