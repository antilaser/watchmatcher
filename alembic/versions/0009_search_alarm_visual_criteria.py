"""Add visual criteria to search alarms."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_alarm_visual"
down_revision = "0008_visual_attributes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_alarms", sa.Column("dial_color", sa.String(64), nullable=True))
    op.add_column("search_alarms", sa.Column("bezel_color", sa.String(64), nullable=True))
    op.add_column("search_alarms", sa.Column("case_material", sa.String(64), nullable=True))
    op.add_column("search_alarms", sa.Column("bracelet_type", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("search_alarms", "bracelet_type")
    op.drop_column("search_alarms", "case_material")
    op.drop_column("search_alarms", "bezel_color")
    op.drop_column("search_alarms", "dial_color")
