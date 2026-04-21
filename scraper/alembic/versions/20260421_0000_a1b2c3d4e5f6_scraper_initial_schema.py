"""Scraper initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-21 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── scraper_sources ────────────────────────────────────────────────────────
    op.create_table(
        "scraper_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", name="uq_scraper_sources_name"),
    )

    # ── scraper_categories ─────────────────────────────────────────────────────
    op.create_table(
        "scraper_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["scraper_sources.id"],
            ondelete="CASCADE",
            name="fk_scraper_categories_source_id",
        ),
    )
    op.create_index(
        "ix_scraper_categories_source_id", "scraper_categories", ["source_id"]
    )

    # ── scraper_brands ─────────────────────────────────────────────────────────
    op.create_table(
        "scraper_brands",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["scraper_sources.id"],
            ondelete="CASCADE",
            name="fk_scraper_brands_source_id",
        ),
    )
    op.create_index(
        "ix_scraper_brands_source_id", "scraper_brands", ["source_id"]
    )

    # ── scraper_products ───────────────────────────────────────────────────────
    op.create_table(
        "scraper_products",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("scraper_category_id", sa.BigInteger(), nullable=True),
        sa.Column("scraper_brand_id", sa.BigInteger(), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("name", sa.String(1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specifications", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column("hash", sa.String(255), nullable=True),
        sa.Column(
            "is_synced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["scraper_sources.id"],
            ondelete="CASCADE",
            name="fk_scraper_products_source_id",
        ),
        sa.ForeignKeyConstraint(
            ["scraper_category_id"],
            ["scraper_categories.id"],
            ondelete="SET NULL",
            name="fk_scraper_products_category_id",
        ),
        sa.ForeignKeyConstraint(
            ["scraper_brand_id"],
            ["scraper_brands.id"],
            ondelete="SET NULL",
            name="fk_scraper_products_brand_id",
        ),
    )
    op.create_index(
        "ix_scraper_products_source_id", "scraper_products", ["source_id"]
    )
    op.create_index(
        "ix_scraper_products_category_id", "scraper_products", ["scraper_category_id"]
    )
    op.create_index(
        "ix_scraper_products_brand_id", "scraper_products", ["scraper_brand_id"]
    )
    op.create_index(
        "ix_scraper_products_is_synced", "scraper_products", ["is_synced"]
    )
    # Composite dedup indexes
    op.create_index(
        "ix_scraper_products_source_external_id",
        "scraper_products",
        ["source_id", "external_id"],
    )
    op.create_index(
        "ix_scraper_products_source_url",
        "scraper_products",
        ["source_id", "source_url"],
    )
    op.create_index(
        "ix_scraper_products_source_sku",
        "scraper_products",
        ["source_id", "sku"],
    )

    # ── scraper_sync_logs ──────────────────────────────────────────────────────
    op.create_table(
        "scraper_sync_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scraper_product_id", sa.BigInteger(), nullable=False),
        sa.Column("sync_status", sa.String(50), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["scraper_product_id"],
            ["scraper_products.id"],
            ondelete="CASCADE",
            name="fk_scraper_sync_logs_product_id",
        ),
    )
    op.create_index(
        "ix_scraper_sync_logs_product_id",
        "scraper_sync_logs",
        ["scraper_product_id"],
    )


def downgrade() -> None:
    op.drop_table("scraper_sync_logs")
    op.drop_table("scraper_products")
    op.drop_table("scraper_brands")
    op.drop_table("scraper_categories")
    op.drop_table("scraper_sources")
