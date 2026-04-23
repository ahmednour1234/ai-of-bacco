"""
20260324_1200_feedback_audit.py
Alembic migration: create extraction_feedback_events audit table.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "e1f2a3b4c5d6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extraction_feedback_events",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
        ),
        sa.Column(
            "candidate_id",
            sa.UUID(),
            sa.ForeignKey("extraction_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("extraction_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column(
            "event_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_feedback_events_candidate_id",
        "extraction_feedback_events",
        ["candidate_id"],
    )
    op.create_index(
        "ix_feedback_events_session_id",
        "extraction_feedback_events",
        ["session_id"],
    )
    op.create_index(
        "ix_feedback_events_user_id",
        "extraction_feedback_events",
        ["user_id"],
    )
    op.create_index(
        "ix_feedback_events_event_type",
        "extraction_feedback_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_events_event_type", table_name="extraction_feedback_events")
    op.drop_index("ix_feedback_events_user_id", table_name="extraction_feedback_events")
    op.drop_index("ix_feedback_events_session_id", table_name="extraction_feedback_events")
    op.drop_index("ix_feedback_events_candidate_id", table_name="extraction_feedback_events")
    op.drop_table("extraction_feedback_events")
