"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "source_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("external_group_id", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("group_type", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_account_id", "external_group_id", name="uq_groups_account_extid"),
    )

    op.create_table(
        "raw_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("sender_external_id", sa.String(255), nullable=True),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("original_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("dedupe_hash", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("group_id", "external_message_id", name="uq_raw_messages_group_extid"),
    )
    op.create_index("ix_raw_messages_dedupe_hash", "raw_messages", ["dedupe_hash"])
    op.create_index("ix_raw_messages_original_ts", "raw_messages", ["original_timestamp"])
    op.create_index("ix_raw_messages_processing_status", "raw_messages", ["processing_status"])

    op.create_table(
        "parsed_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("classification_confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("parse_method", sa.String(16), nullable=False),
        sa.Column("parse_confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "watch_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand", sa.String(128), nullable=False, index=True),
        sa.Column("family", sa.String(255), nullable=False, index=True),
        sa.Column("reference", sa.String(64), nullable=False, index=True),
        sa.Column("nickname", sa.String(128), nullable=True),
        sa.Column("aliases_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("brand", "family", "reference", name="uq_watch_entities_b_f_r"),
    )

    op.create_table(
        "watch_entity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("watch_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watch_entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("alias_text", sa.String(255), nullable=False, index=True),
        sa.Column("alias_type", sa.String(32), nullable=False),
        sa.Column("confidence_weight", sa.Numeric(5, 4), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("watch_entity_id", "alias_text", name="uq_alias_entity_text"),
    )

    op.create_table(
        "sell_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parsed_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parsed_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("watch_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watch_entities.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("brand_raw", sa.String(128), nullable=True),
        sa.Column("family_raw", sa.String(255), nullable=True),
        sa.Column("reference_raw", sa.String(64), nullable=True),
        sa.Column("condition_raw", sa.String(128), nullable=True),
        sa.Column("set_completeness_raw", sa.String(128), nullable=True),
        sa.Column("asking_price", sa.Numeric(12, 2), nullable=True, index=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("location_raw", sa.String(255), nullable=True),
        sa.Column("seller_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("negotiable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE", index=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "buy_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parsed_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parsed_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("watch_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watch_entities.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("brand_raw", sa.String(128), nullable=True),
        sa.Column("family_raw", sa.String(255), nullable=True),
        sa.Column("reference_raw", sa.String(64), nullable=True),
        sa.Column("condition_raw", sa.String(128), nullable=True),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=True, index=True),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("location_raw", sa.String(255), nullable=True),
        sa.Column("buyer_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN", index=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sell_offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sell_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buy_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buy_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watch_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watch_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("match_type", sa.String(32), nullable=False),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("seller_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("buyer_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("seller_currency", sa.String(8), nullable=True),
        sa.Column("buyer_currency", sa.String(8), nullable=True),
        sa.Column("fx_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("risk_buffer", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("reasoning_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sell_offer_id", "buy_request_id", name="uq_matches_offer_request"),
    )
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_expected_profit", "matches", ["expected_profit"])

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matches.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("alert_type", sa.String(48), nullable=False, index=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING", index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "review_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(32), nullable=False, index=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("action_type", sa.String(48), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_embeddings_object", "embeddings", ["object_type", "object_id"])


def downgrade() -> None:
    op.drop_index("ix_embeddings_object", table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_table("review_actions")
    op.drop_table("alerts")
    op.drop_index("ix_matches_expected_profit", table_name="matches")
    op.drop_index("ix_matches_status", table_name="matches")
    op.drop_table("matches")
    op.drop_table("buy_requests")
    op.drop_table("sell_offers")
    op.drop_table("watch_entity_aliases")
    op.drop_table("watch_entities")
    op.drop_table("parsed_messages")
    op.drop_index("ix_raw_messages_processing_status", table_name="raw_messages")
    op.drop_index("ix_raw_messages_original_ts", table_name="raw_messages")
    op.drop_index("ix_raw_messages_dedupe_hash", table_name="raw_messages")
    op.drop_table("raw_messages")
    op.drop_table("groups")
    op.drop_table("source_accounts")
    op.drop_table("workspaces")
