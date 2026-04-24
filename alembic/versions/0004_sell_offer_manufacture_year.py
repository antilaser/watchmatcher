"""Add manufacture_year on sell_offers for listings / filters."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_sell_offer_manufacture_year"
down_revision = "0003_match_human_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sell_offers",
        sa.Column("manufacture_year", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sell_offers_manufacture_year",
        "sell_offers",
        ["manufacture_year"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sell_offers_manufacture_year", table_name="sell_offers")
    op.drop_column("sell_offers", "manufacture_year")
