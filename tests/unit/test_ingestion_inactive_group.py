from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.enums import GroupType, ProcessingStatus, SourceType
from app.ingestion.dedupe import compute_dedupe_hash
from app.ingestion.service import IngestionService
from app.models import Group, RawMessage, SourceAccount
from app.schemas.message import IncomingMessage
from app.services.pipeline import PipelineService


@pytest.mark.asyncio
async def test_ingest_skips_when_group_is_inactive(session, workspace):
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="t-src",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    g = Group(
        workspace_id=workspace.id,
        source_account_id=src.id,
        external_group_id="120363@g.us",
        group_name="Muted",
        group_type=GroupType.UNKNOWN,
        is_active=False,
    )
    session.add(g)
    await session.commit()

    ingestion = IngestionService(session)
    msg = IncomingMessage(
        external_message_id="m-1",
        external_group_id="120363@g.us",
        group_name="Muted",
        sender_name="U",
        text_body="FS 126610 10k",
        original_timestamp=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    row, created = await ingestion.ingest(workspace, src, msg)
    assert row is None
    assert created is False


@pytest.mark.asyncio
async def test_ingest_batch_counts_inactive_separately(session, workspace):
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="t-src2",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    inactive_gid = "111@g.us"
    session.add(
        Group(
            workspace_id=workspace.id,
            source_account_id=src.id,
            external_group_id=inactive_gid,
            group_name="Off",
            group_type=GroupType.UNKNOWN,
            is_active=False,
        )
    )
    await session.commit()

    ingestion = IngestionService(session)
    ts = datetime(2026, 4, 20, tzinfo=timezone.utc)
    msgs = [
        IncomingMessage(
            external_message_id="a",
            external_group_id=inactive_gid,
            group_name="Off",
            sender_name="U",
            text_body="hello",
            original_timestamp=ts,
        ),
        IncomingMessage(
            external_message_id="b",
            external_group_id="222@g.us",
            group_name="On",
            sender_name="U",
            text_body="hello",
            original_timestamp=ts,
        ),
    ]
    created, dupes, inactive, _p = await ingestion.ingest_batch(workspace, src, msgs)
    assert inactive == 1
    assert dupes == 0
    assert len(created) == 1


@pytest.mark.asyncio
async def test_pipeline_skips_raw_when_group_inactive(session, workspace):
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="t-pipe",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    g = Group(
        workspace_id=workspace.id,
        source_account_id=src.id,
        external_group_id="999@g.us",
        group_name="X",
        group_type=GroupType.UNKNOWN,
        is_active=False,
    )
    session.add(g)
    await session.flush()

    ts = datetime(2026, 4, 21, tzinfo=timezone.utc)
    raw = RawMessage(
        workspace_id=workspace.id,
        group_id=g.id,
        external_message_id="q-1",
        text_body="WTB 126610",
        message_type="text",
        original_timestamp=ts,
        ingested_at=ts,
        metadata_json={},
        dedupe_hash=compute_dedupe_hash("t-pipe", "999@g.us", "q-1", "WTB 126610", ts),
        processing_status=ProcessingStatus.PENDING,
    )
    session.add(raw)
    await session.commit()

    await PipelineService(session).process_raw_message(raw.id)
    await session.refresh(raw)
    assert raw.processing_status == ProcessingStatus.COMPLETED
    assert (raw.metadata_json or {}).get("skipped_reason") == "inactive_group"
