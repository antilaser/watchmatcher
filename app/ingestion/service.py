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
        invite_code: str | None = None,
    ) -> Group:
        stmt = select(Group).where(
            Group.source_account_id == source_account.id,
            Group.external_group_id == external_group_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            if invite_code and not existing.invite_code:
                existing.invite_code = invite_code
            return existing

        group = Group(
            workspace_id=workspace_id,
            source_account_id=source_account.id,
            external_group_id=external_group_id,
            invite_code=invite_code,
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
    ) -> tuple[RawMessage | None, bool]:
        """Insert a raw message; return (row, created).

        Idempotent: the same message hash will not be stored twice.
        If the group is disabled in the dashboard (`is_active=False`), returns
        ``(None, False)`` and does not persist anything.
        """
        group = await self.get_or_create_group(
            workspace_id=workspace.id,
            source_account=source_account,
            external_group_id=message.external_group_id,
            group_name=message.group_name,
            invite_code=message.group_invite_code,
        )
        if not group.is_active:
            log.info(
                "ingest_skipped_inactive_group",
                external_group_id=message.external_group_id,
                group_id=str(group.id),
            )
            return None, False

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

        meta = dict(message.metadata)
        if message.image_base64:
            meta["has_ingest_image"] = True
        if message.image_mime_type:
            meta["image_mime_type"] = message.image_mime_type

        row = RawMessage(
            workspace_id=workspace.id,
            group_id=group.id,
            external_message_id=message.external_message_id,
            sender_name=message.sender_name,
            sender_external_id=message.sender_external_id,
            text_body=message.text_body or "",
            message_type=message.message_type,
            original_timestamp=message.original_timestamp,
            ingested_at=datetime.now(timezone.utc),
            metadata_json=meta,
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
    ) -> tuple[list[RawMessage], int, int, list[tuple[UUID, str, str]]]:
        """Returns (created_rows, skipped_duplicates, skipped_inactive_groups, pending_images).

        Each pending image is ``(raw_message_id, base64, mime_type)`` for Redis
        after the transaction commits.
        """
        created: list[RawMessage] = []
        pending_images: list[tuple[UUID, str, str]] = []
        skipped_duplicates = 0
        skipped_inactive = 0
        for m in messages:
            row, was_created = await self.ingest(workspace, source_account, m)
            if row is None:
                skipped_inactive += 1
                continue
            if was_created:
                created.append(row)
                if m.image_base64 and m.image_base64.strip():
                    pending_images.append(
                        (
                            row.id,
                            m.image_base64.strip(),
                            m.image_mime_type or "image/jpeg",
                        )
                    )
            else:
                skipped_duplicates += 1
        return created, skipped_duplicates, skipped_inactive, pending_images
