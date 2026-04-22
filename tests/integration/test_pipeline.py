from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.enums import (
    BuyRequestStatus,
    MessageClassification,
    SellOfferStatus,
    SourceType,
)
from app.ingestion.service import IngestionService
from app.models import (
    Alert,
    BuyRequest,
    Match,
    ParsedMessage,
    SellOffer,
    SourceAccount,
)
from app.normalization.catalog_loader import load_catalog
from app.schemas.message import IncomingMessage
from app.services.pipeline import PipelineService

SEED = Path(__file__).resolve().parent.parent.parent / "app" / "seed" / "data" / "watch_catalog.json"


@pytest.mark.asyncio
async def test_end_to_end_match_creates_alert(session, workspace):
    await load_catalog(session, SEED)

    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="fake",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    seller_msg = IncomingMessage(
        external_message_id="s-1",
        external_group_id="sellers",
        group_name="Sellers",
        sender_name="Marco",
        text_body="FS Rolex 126610LV Starbucks, full set, €13500 firm",
        original_timestamp=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    )
    buyer_msg = IncomingMessage(
        external_message_id="b-1",
        external_group_id="buyers",
        group_name="Buyers",
        sender_name="Anna",
        text_body="WTB Rolex Starbucks 126610LV, budget 14500 EUR",
        original_timestamp=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
    )

    ingestion = IngestionService(session)
    seller_row, _ = await ingestion.ingest(workspace, src, seller_msg)
    buyer_row, _ = await ingestion.ingest(workspace, src, buyer_msg)
    await session.flush()

    pipeline = PipelineService(session)
    await pipeline.process_raw_message(seller_row.id)
    await pipeline.process_raw_message(buyer_row.id)
    await session.flush()

    parsed = (await session.execute(select(ParsedMessage))).scalars().all()
    assert len(parsed) == 2
    assert {p.classification for p in parsed} == {
        MessageClassification.SELL_OFFER,
        MessageClassification.BUY_REQUEST,
    }

    offers = (await session.execute(select(SellOffer))).scalars().all()
    requests = (await session.execute(select(BuyRequest))).scalars().all()
    assert len(offers) == 1
    assert len(requests) == 1
    assert offers[0].status == SellOfferStatus.ACTIVE
    assert requests[0].status == BuyRequestStatus.OPEN
    assert offers[0].watch_entity_id is not None
    assert offers[0].watch_entity_id == requests[0].watch_entity_id

    matches = (await session.execute(select(Match))).scalars().all()
    assert len(matches) == 1
    assert matches[0].expected_profit is not None
    assert matches[0].expected_profit > 0

    alerts = (await session.execute(select(Alert))).scalars().all()
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_unpriced_buy_request_remains_open(session, workspace):
    await load_catalog(session, SEED)
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="fake",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    msg = IncomingMessage(
        external_message_id="b-2",
        external_group_id="buyers",
        sender_name="Pierre",
        text_body="Looking for Patek 5711, message me with offers",
        original_timestamp=datetime(2026, 4, 20, 11, 0, tzinfo=timezone.utc),
    )
    ingestion = IngestionService(session)
    row, _ = await ingestion.ingest(workspace, src, msg)
    await session.flush()

    pipeline = PipelineService(session)
    await pipeline.process_raw_message(row.id)
    await session.flush()

    requests = (await session.execute(select(BuyRequest))).scalars().all()
    assert len(requests) == 1
    assert requests[0].status == BuyRequestStatus.OPEN_UNPRICED
    assert requests[0].target_price is None


@pytest.mark.asyncio
async def test_idempotent_ingestion(session, workspace):
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="fake",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    msg = IncomingMessage(
        external_message_id="dup-1",
        external_group_id="g",
        text_body="hello",
        original_timestamp=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    ingestion = IngestionService(session)
    r1, c1 = await ingestion.ingest(workspace, src, msg)
    r2, c2 = await ingestion.ingest(workspace, src, msg)
    assert c1 is True
    assert c2 is False
    assert r1.id == r2.id
