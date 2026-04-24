"""Add optional WhatsApp group invite code for deep links."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_groups_invite_code"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "groups",
        sa.Column("invite_code", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("groups", "invite_code")
