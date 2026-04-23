"""convert_scraper_tables_to_utf8mb4

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 00:01:00.000000

Converts all scraper tables from latin1_swedish_ci to utf8mb4_unicode_ci
so Arabic and other Unicode text can be stored and compared correctly.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "scraper_sources",
    "scraper_categories",
    "scraper_brands",
    "scraper_products",
    "scraper_sync_logs",
]


def upgrade() -> None:
    bind = op.get_bind()
    # Only run on MySQL — SQLite has no charset concept
    if bind.dialect.name != "mysql":
        return
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci"
        )
