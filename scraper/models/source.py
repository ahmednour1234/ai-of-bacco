"""
scraper/models/source.py
-------------------------
Represents an external website that the scraper targets.
One source → many categories, brands, and products.
"""

from __future__ import annotations

from sqlalchemy import Integer, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scraper.core.database import ScraperBase
from scraper.models.base import ScraperTimestampMixin


class ScraperSource(ScraperTimestampMixin, ScraperBase):
    __tablename__ = "scraper_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    categories: Mapped[list["ScraperCategory"]] = relationship(  # noqa: F821
        back_populates="source", lazy="noload", cascade="all, delete-orphan"
    )
    brands: Mapped[list["ScraperBrand"]] = relationship(  # noqa: F821
        back_populates="source", lazy="noload", cascade="all, delete-orphan"
    )
    products: Mapped[list["ScraperProduct"]] = relationship(  # noqa: F821
        back_populates="source", lazy="noload", cascade="all, delete-orphan"
    )
