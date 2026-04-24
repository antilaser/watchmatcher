"""Backfill plain calendar years out of sell offer references."""

from __future__ import annotations

from alembic import op

revision = "0005_backfill_sell_offer_year_refs"
down_revision = "0004_sell_offer_manufacture_year"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sell_offers
        SET
            manufacture_year = COALESCE(manufacture_year, reference_raw::integer),
            reference_raw = NULL,
            updated_at = now()
        WHERE reference_raw ~ '^(19|20)[0-9]{2}$'
        """
    )
    op.execute(
        """
        UPDATE parsed_messages
        SET
            extracted_json = jsonb_set(
                CASE
                    WHEN extracted_json->>'year' IS NULL THEN
                        jsonb_set(
                            extracted_json,
                            '{year}',
                            to_jsonb((extracted_json->>'reference')::integer),
                            true
                        )
                    ELSE extracted_json
                END,
                '{reference}',
                'null'::jsonb,
                true
            ),
            updated_at = now()
        WHERE extracted_json->>'reference' ~ '^(19|20)[0-9]{2}$'
        """
    )


def downgrade() -> None:
    # Data-only correction; restoring ambiguous reference values would be unsafe.
    pass
