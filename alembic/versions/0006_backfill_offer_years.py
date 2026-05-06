"""Backfill sell offer years from parsed JSON."""

from __future__ import annotations

from alembic import op

revision = "0006_backfill_offer_years"
down_revision = "0005_backfill_year_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sell_offers so
        SET
            manufacture_year = (pm.extracted_json->>'year')::integer,
            updated_at = now()
        FROM parsed_messages pm
        WHERE pm.id = so.parsed_message_id
          AND so.manufacture_year IS NULL
          AND pm.extracted_json->>'year' ~ '^(19|20)[0-9]{2}$'
        """
    )


def downgrade() -> None:
    # Data-only backfill; do not erase corrected years.
    pass
