"""
PriceEstimation Model
=====================
Stores AI-generated price estimations for a product.
Sources: historical_invoice, supplier_catalog, web_scrape, manual.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, Float, ForeignKey, JSON, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, TenantMixin


class PriceSourceType(str, enum.Enum):
    HISTORICAL_INVOICE = "historical_invoice"
    SUPPLIER_CATALOG = "supplier_catalog"
    WEB_SCRAPE = "web_scrape"
    AI_ESTIMATED = "ai_estimated"
    MANUAL = "manual"


class PriceEstimation(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "price_estimations"

    # ── FK ────────────────────────────────────────────────────────────────────
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Estimation ────────────────────────────────────────────────────────────
    estimated_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 – 1.0

    source_type: Mapped[PriceSourceType] = mapped_column(
        Enum(PriceSourceType, name="price_source_type_enum"),
        nullable=False,
        default=PriceSourceType.AI_ESTIMATED,
        index=True,
    )

    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Extra Context ─────────────────────────────────────────────────────────
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────────
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="price_estimations", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<PriceEstimation product={self.product_id} price={self.estimated_price} source={self.source_type}>"
