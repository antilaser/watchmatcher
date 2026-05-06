"""Add saved search alarms."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_search_alarms"
down_revision = "0006_backfill_offer_years"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_alarms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False, server_default="SELL"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("brand", sa.String(128), nullable=True),
        sa.Column("reference", sa.String(64), nullable=True),
        sa.Column("year_min", sa.Integer(), nullable=True),
        sa.Column("year_max", sa.Integer(), nullable=True),
        sa.Column("price_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("extra_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_search_alarms_workspace_id", "search_alarms", ["workspace_id"])
    op.create_index("ix_search_alarms_target_type", "search_alarms", ["target_type"])
    op.create_index("ix_search_alarms_is_active", "search_alarms", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_search_alarms_is_active", table_name="search_alarms")
    op.drop_index("ix_search_alarms_target_type", table_name="search_alarms")
    op.drop_index("ix_search_alarms_workspace_id", table_name="search_alarms")
    op.drop_table("search_alarms")
