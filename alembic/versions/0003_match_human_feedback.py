"""Add human feedback columns on matches for dashboard training."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_match_human_feedback"
down_revision = "0002_groups_invite_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("human_feedback", sa.String(length=8), nullable=True))
    op.add_column("matches", sa.Column("human_feedback_note", sa.Text(), nullable=True))
    op.add_column(
        "matches",
        sa.Column("human_feedback_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_matches_human_feedback", "matches", ["human_feedback"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_matches_human_feedback", table_name="matches")
    op.drop_column("matches", "human_feedback_at")
    op.drop_column("matches", "human_feedback_note")
    op.drop_column("matches", "human_feedback")
