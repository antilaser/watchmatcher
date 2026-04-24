from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.enums import (
    BuyRequestStatus,
    MessageClassification,
    ParseMethod,
    ProcessingStatus,
    SellOfferStatus,
    SourceType,
)
from app.matching.candidate_search import find_open_buy_requests_for_offer
from app.models import (
    BuyRequest,
    Group,
    ParsedMessage,
    RawMessage,
    SellOffer,
    SourceAccount,
)


@pytest.mark.asyncio
async def test_buy_request_older_than_cutoff_not_matched(session, workspace):
    now = datetime.now(timezone.utc)
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=SourceType.FAKE,
        account_name="age-test",
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.flush()

    g = Group(
        workspace_id=workspace.id,
        source_account_id=src.id,
        external_group_id="g1@g.us",
        group_name="G",
        is_active=True,
    )
    session.add(g)
    await session.flush()

    def raw_row(ext_id: str, ts: datetime, body: str) -> RawMessage:
        return RawMessage(
            workspace_id=workspace.id,
            group_id=g.id,
            external_message_id=ext_id,
            text_body=body,
            message_type="text",
            original_timestamp=ts,
            ingested_at=now,
            metadata_json={},
            dedupe_hash=f"deadbeef{ext_id}",
            processing_status=ProcessingStatus.COMPLETED,
        )

    r_old = raw_row("old", now - timedelta(days=14), "WTB 126610LV")
    r_new = raw_row("new", now - timedelta(days=2), "WTB 126610LV")
    r_sell = raw_row("sell", now - timedelta(hours=1), "FS 126610LV 12k")
    session.add_all([r_old, r_new, r_sell])
    await session.flush()

    p_old = ParsedMessage(
        raw_message_id=r_old.id,
        classification=MessageClassification.BUY_REQUEST,
        classification_confidence=0.8,
        parse_method=ParseMethod.RULE,
        parse_confidence=0.8,
        extracted_json={},
    )
    p_new = ParsedMessage(
        raw_message_id=r_new.id,
        classification=MessageClassification.BUY_REQUEST,
        classification_confidence=0.8,
        parse_method=ParseMethod.RULE,
        parse_confidence=0.8,
        extracted_json={},
    )
    p_sell = ParsedMessage(
        raw_message_id=r_sell.id,
        classification=MessageClassification.SELL_OFFER,
        classification_confidence=0.8,
        parse_method=ParseMethod.RULE,
        parse_confidence=0.8,
        extracted_json={},
    )
    session.add_all([p_old, p_new, p_sell])
    await session.flush()

    b_old = BuyRequest(
        workspace_id=workspace.id,
        raw_message_id=r_old.id,
        parsed_message_id=p_old.id,
        reference_raw="126610LV",
        status=BuyRequestStatus.OPEN_UNPRICED,
        confidence=0.8,
    )
    b_new = BuyRequest(
        workspace_id=workspace.id,
        raw_message_id=r_new.id,
        parsed_message_id=p_new.id,
        reference_raw="126610LV",
        status=BuyRequestStatus.OPEN_UNPRICED,
        confidence=0.8,
    )
    offer = SellOffer(
        workspace_id=workspace.id,
        raw_message_id=r_sell.id,
        parsed_message_id=p_sell.id,
        reference_raw="126610LV",
        asking_price=Decimal("12000"),
        currency="USD",
        status=SellOfferStatus.ACTIVE,
        confidence=0.8,
    )
    session.add_all([b_old, b_new, offer])
    await session.commit()

    cutoff = now - timedelta(days=7)
    hits = await find_open_buy_requests_for_offer(
        session,
        offer,
        counterpart_message_not_before=cutoff,
    )
    ids = {h.id for h in hits}
    assert b_new.id in ids
    assert b_old.id not in ids
