"""Add visual watch attributes for color-aware matching."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_visual_attributes"
down_revision = "0007_search_alarms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("sell_offers", "buy_requests"):
        op.add_column(table, sa.Column("dial_color", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("bezel_color", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("case_material", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("bracelet_type", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("visual_confidence", sa.Numeric(5, 4), nullable=True))
        op.create_index(f"ix_{table}_dial_color", table, ["dial_color"])


def downgrade() -> None:
    for table in ("buy_requests", "sell_offers"):
        op.drop_index(f"ix_{table}_dial_color", table_name=table)
        op.drop_column(table, "visual_confidence")
        op.drop_column(table, "bracelet_type")
        op.drop_column(table, "case_material")
        op.drop_column(table, "bezel_color")
        op.drop_column(table, "dial_color")
