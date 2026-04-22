"""Ingestion service — turns IncomingMessage into RawMessage rows idempotently."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupType, ProcessingStatus
from app.core.logging import get_logger
from app.ingestion.dedupe import compute_dedupe_hash
from app.models import Group, RawMessage, SourceAccount, Workspace
from app.schemas.message import IncomingMessage

log = get_logger(__name__)


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_group(
        self,
        workspace_id: UUID,
        source_account: SourceAccount,
        external_group_id: str,
        group_name: str | None,
    ) -> Group:
        stmt = select(Group).where(
            Group.source_account_id == source_account.id,
            Group.external_group_id == external_group_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        group = Group(
            workspace_id=workspace_id,
            source_account_id=source_account.id,
            external_group_id=external_group_id,
            group_name=group_name or external_group_id,
            group_type=GroupType.UNKNOWN,
            is_active=True,
        )
        self.session.add(group)
        await self.session.flush()
        return group

    async def ingest(
        self,
        workspace: Workspace,
        source_account: SourceAccount,
        message: IncomingMessage,
    ) -> tuple[RawMessage, bool]:
        """Insert a raw message; return (row, created).

        Idempotent: the same message hash will not be stored twice.
        """
        group = await self.get_or_create_group(
            workspace_id=workspace.id,
            source_account=source_account,
            external_group_id=message.external_group_id,
            group_name=message.group_name,
        )

        dedupe = compute_dedupe_hash(
            source_account=source_account.account_name,
            external_group_id=message.external_group_id,
            external_message_id=message.external_message_id,
            text_body=message.text_body,
            original_timestamp=message.original_timestamp,
        )

        existing = (
            await self.session.execute(
                select(RawMessage).where(RawMessage.dedupe_hash == dedupe)
            )
        ).scalar_one_or_none()
        if existing:
            return existing, False

        row = RawMessage(
            workspace_id=workspace.id,
            group_id=group.id,
            external_message_id=message.external_message_id,
            sender_name=message.sender_name,
            sender_external_id=message.sender_external_id,
            text_body=message.text_body,
            message_type=message.message_type,
            original_timestamp=message.original_timestamp,
            ingested_at=datetime.now(timezone.utc),
            metadata_json=message.metadata,
            dedupe_hash=dedupe,
            processing_status=ProcessingStatus.PENDING,
        )
        self.session.add(row)
        await self.session.flush()
        log.info(
            "raw_message_ingested",
            raw_message_id=str(row.id),
            group_id=str(group.id),
            dedupe_hash=dedupe,
        )
        return row, True

    async def ingest_batch(
        self,
        workspace: Workspace,
        source_account: SourceAccount,
        messages: list[IncomingMessage],
    ) -> tuple[list[RawMessage], int]:
        """Returns (created_rows, skipped_count)."""
        created: list[RawMessage] = []
        skipped = 0
        for m in messages:
            row, was_created = await self.ingest(workspace, source_account, m)
            if was_created:
                created.append(row)
            else:
                skipped += 1
        return created, skipped
