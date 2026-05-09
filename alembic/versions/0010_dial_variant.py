"""Add dial variant for stricter visual matching."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_dial_variant"
down_revision = "0009_alarm_visual"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("sell_offers", "buy_requests"):
        op.add_column(table, sa.Column("dial_variant", sa.String(64), nullable=True))
        op.create_index(f"ix_{table}_dial_variant", table, ["dial_variant"])


def downgrade() -> None:
    for table in ("buy_requests", "sell_offers"):
        op.drop_index(f"ix_{table}_dial_variant", table_name=table)
        op.drop_column(table, "dial_variant")
