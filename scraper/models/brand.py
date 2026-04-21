"""
scraper/models/brand.py
------------------------
Product brand as scraped from the source website.
Stored locally in the scraper database.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scraper.core.database import ScraperBase
from scraper.models.base import ScraperTimestampMixin


class ScraperBrand(ScraperTimestampMixin, ScraperBase):
    __tablename__ = "scraper_brands"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("scraper_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    source: Mapped["ScraperSource"] = relationship(  # noqa: F821
        back_populates="brands", lazy="noload"
    )
    products: Mapped[list["ScraperProduct"]] = relationship(  # noqa: F821
        back_populates="brand", lazy="noload"
    )
