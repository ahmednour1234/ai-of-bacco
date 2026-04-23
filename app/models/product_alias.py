"""
ProductAlias Model
==================
Stores alternative names / synonyms for a product.
The embedding column is pgvector-ready for semantic similarity search.

To activate embeddings:
    1. Install pgvector on your Postgres server
    2. Run: CREATE EXTENSION IF NOT EXISTS vector;
    3. Uncomment the embedding column below and regenerate the migration.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, TenantMixin

# Uncomment when pgvector extension is installed:
# from pgvector.sqlalchemy import Vector


class ProductAlias(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "product_aliases"

    # ── FK ────────────────────────────────────────────────────────────────────
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Alias ─────────────────────────────────────────────────────────────────
    alias_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # e.g. "invoice", "supplier_catalog", "manual"
    language: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default="en"
    )

    # ── pgvector (1536-dim, OpenAI ada-002 / text-embedding-3-small) ──────────
    # Uncomment after enabling the pgvector extension + running a migration:
    # embedding: Mapped[list[float] | None] = mapped_column(
    #     Vector(1536), nullable=True
    # )

    # ── Relationships ─────────────────────────────────────────────────────────
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="aliases", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<ProductAlias id={self.id} alias={self.alias_text!r}>"
