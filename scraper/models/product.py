"""
scraper/models/product.py
--------------------------
A product collected from a source website.

Duplicate detection (handled in ProductRepository.upsert_product):
    1. source_id + external_id      (highest priority)
    2. source_id + source_url
    3. source_id + sku              (lowest priority)

is_synced is reset to False whenever the content hash changes on update,
so the sync service will re-send updated products automatically.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scraper.core.database import ScraperBase
from scraper.models.base import ScraperTimestampMixin


class ScraperProduct(ScraperTimestampMixin, ScraperBase):
    __tablename__ = "scraper_products"
    __table_args__ = (
        # Composite indexes for dedup lookups
        Index("ix_scraper_products_source_external_id", "source_id", "external_id"),
        Index("ix_scraper_products_source_url", "source_id", "source_url"),
        Index("ix_scraper_products_source_sku", "source_id", "sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Foreign keys ───────────────────────────────────────────────────────────
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scraper_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scraper_category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scraper_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scraper_brand_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scraper_brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Product identity ───────────────────────────────────────────────────────
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Product data ───────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Content fingerprint ────────────────────────────────────────────────────
    hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Sync state ─────────────────────────────────────────────────────────────
    is_synced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
    synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    source: Mapped["ScraperSource"] = relationship(  # noqa: F821
        back_populates="products", lazy="noload"
    )
    category: Mapped[Optional["ScraperCategory"]] = relationship(  # noqa: F821
        back_populates="products", lazy="noload"
    )
    brand: Mapped[Optional["ScraperBrand"]] = relationship(  # noqa: F821
        back_populates="products", lazy="noload"
    )
    sync_logs: Mapped[list["ScraperSyncLog"]] = relationship(  # noqa: F821
        back_populates="product", lazy="noload", cascade="all, delete-orphan"
    )
