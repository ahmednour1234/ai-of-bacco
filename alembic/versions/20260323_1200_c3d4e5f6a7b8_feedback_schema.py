"""feedback_schema

Revision ID: c3d4e5f6a7b8
Revises: b2b2972d979f
Create Date: 2026-03-23 12:00:00.000000

Creates the four tables required by the feedback-driven extraction system:
  - extraction_sessions    tracks one upload job
  - extraction_candidates  one row per extracted line / table cell
  - learned_rules          dynamic keyword/pattern rules updated by user feedback
  - correction_examples    approved product examples used for similarity lookup
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2b2972d979f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── extraction_sessions ───────────────────────────────────────────────────
    op.create_table(
        "extraction_sessions",
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("total_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extraction_sessions_id"), "extraction_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_extraction_sessions_status"), "extraction_sessions", ["status"], unique=False)

    # ── extraction_candidates ─────────────────────────────────────────────────
    op.create_table(
        "extraction_candidates",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        # Machine prediction
        sa.Column("predicted_label", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("product_name", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default="false"),
        # Human correction
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("corrected_label", sa.String(length=32), nullable=True),
        sa.Column("corrected_name", sa.String(length=512), nullable=True),
        sa.Column("corrected_description", sa.Text(), nullable=True),
        sa.Column("corrected_quantity", sa.Float(), nullable=True),
        sa.Column("corrected_unit", sa.String(length=64), nullable=True),
        sa.Column("corrected_brand", sa.String(length=255), nullable=True),
        sa.Column("corrected_category", sa.String(length=255), nullable=True),
        sa.Column("corrected_price", sa.Float(), nullable=True),
        sa.Column("correction_note", sa.Text(), nullable=True),
        # Common
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["extraction_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extraction_candidates_id"), "extraction_candidates", ["id"], unique=False)
    op.create_index(op.f("ix_extraction_candidates_session_id"), "extraction_candidates", ["session_id"], unique=False)
    op.create_index(op.f("ix_extraction_candidates_predicted_label"), "extraction_candidates", ["predicted_label"], unique=False)
    op.create_index(op.f("ix_extraction_candidates_status"), "extraction_candidates", ["status"], unique=False)

    # ── learned_rules ─────────────────────────────────────────────────────────
    op.create_table(
        "learned_rules",
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("rule_value", sa.String(length=512), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="user_correction"),
        sa.Column("examples_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_hint", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_type", "rule_value", name="uq_learned_rules_type_value"),
    )
    op.create_index(op.f("ix_learned_rules_id"), "learned_rules", ["id"], unique=False)
    op.create_index(op.f("ix_learned_rules_rule_type"), "learned_rules", ["rule_type"], unique=False)
    op.create_index(op.f("ix_learned_rules_is_active"), "learned_rules", ["is_active"], unique=False)

    # ── correction_examples ───────────────────────────────────────────────────
    op.create_table(
        "correction_examples",
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.String(length=1024), nullable=False),
        sa.Column("correct_label", sa.String(length=32), nullable=False),
        sa.Column("correct_name", sa.String(length=512), nullable=True),
        sa.Column("correct_description", sa.Text(), nullable=True),
        sa.Column("correct_quantity", sa.Float(), nullable=True),
        sa.Column("correct_unit", sa.String(length=64), nullable=True),
        sa.Column("correct_brand", sa.String(length=255), nullable=True),
        sa.Column("correct_category", sa.String(length=255), nullable=True),
        sa.Column("correct_price", sa.Float(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_correction_examples_id"), "correction_examples", ["id"], unique=False)
    op.create_index(op.f("ix_correction_examples_normalized_text"), "correction_examples", ["normalized_text"], unique=False)
    op.create_index(op.f("ix_correction_examples_correct_label"), "correction_examples", ["correct_label"], unique=False)


def downgrade() -> None:
    op.drop_table("correction_examples")
    op.drop_table("learned_rules")
    op.drop_table("extraction_candidates")
    op.drop_table("extraction_sessions")
