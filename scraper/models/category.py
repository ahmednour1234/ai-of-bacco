"""
scraper/models/category.py
---------------------------
Product category as scraped from the source website.
Stored locally in the scraper database.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scraper.core.database import ScraperBase
from scraper.models.base import ScraperTimestampMixin


class ScraperCategory(ScraperTimestampMixin, ScraperBase):
    __tablename__ = "scraper_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("scraper_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    source: Mapped["ScraperSource"] = relationship(  # noqa: F821
        back_populates="categories", lazy="noload"
    )
    products: Mapped[list["ScraperProduct"]] = relationship(  # noqa: F821
        back_populates="category", lazy="noload"
    )
