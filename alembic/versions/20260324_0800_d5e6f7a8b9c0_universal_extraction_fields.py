"""universal_extraction_fields

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-03-24 08:00:00.000000

Adds columns required by the UniversalExtractionPipeline (6-stage: parse →
detect → region → classify → extract):

  extraction_sessions:
    - contains_products     (Boolean, nullable)
    - document_type_guess   (String 64, nullable)
    - detection_confidence  (Float, nullable)
    - detection_metadata    (JSONB, nullable)

  extraction_candidates:
    - region_id             (String 64, nullable)
    - region_type           (String 64, nullable)
    - page_number           (Integer, nullable)
    - coordinates           (JSONB, nullable)  — {x0, y0, x1, y1, page}
    - classification_source (String 32, nullable)  — "llm" | "heuristic"
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── extraction_sessions ───────────────────────────────────────────────────
    op.add_column(
        "extraction_sessions",
        sa.Column("contains_products", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "extraction_sessions",
        sa.Column("document_type_guess", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "extraction_sessions",
        sa.Column("detection_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "extraction_sessions",
        sa.Column("detection_metadata", JSONB(), nullable=True),
    )

    # ── extraction_candidates ─────────────────────────────────────────────────
    op.add_column(
        "extraction_candidates",
        sa.Column("region_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "extraction_candidates",
        sa.Column("region_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "extraction_candidates",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extraction_candidates",
        sa.Column("coordinates", JSONB(), nullable=True),
    )
    op.add_column(
        "extraction_candidates",
        sa.Column("classification_source", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    # ── extraction_candidates ─────────────────────────────────────────────────
    op.drop_column("extraction_candidates", "classification_source")
    op.drop_column("extraction_candidates", "coordinates")
    op.drop_column("extraction_candidates", "page_number")
    op.drop_column("extraction_candidates", "region_type")
    op.drop_column("extraction_candidates", "region_id")

    # ── extraction_sessions ───────────────────────────────────────────────────
    op.drop_column("extraction_sessions", "detection_metadata")
    op.drop_column("extraction_sessions", "detection_confidence")
    op.drop_column("extraction_sessions", "document_type_guess")
    op.drop_column("extraction_sessions", "contains_products")
