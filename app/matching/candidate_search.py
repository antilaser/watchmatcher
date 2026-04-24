"""Candidate search: find counterparts for a new offer or request."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import BuyRequestStatus, SellOfferStatus
from app.models import BuyRequest, RawMessage, SellOffer


ACTIVE_OFFER_STATUSES = (SellOfferStatus.ACTIVE,)
OPEN_REQUEST_STATUSES = (BuyRequestStatus.OPEN, BuyRequestStatus.OPEN_UNPRICED)

def _reference_match_clause(column, raw_ref: str | None):
    """Match exact ref or counterpart ref starting with the given ref (ilike ref%)."""
    if not raw_ref or not str(raw_ref).strip():
        return None
    ref = str(raw_ref).strip()
    parts = [
        column.ilike(ref),
        column.ilike(ref + "%"),
    ]
    return or_(*parts)


def _brand_family_clause(brand_col, family_col, brand_raw: str | None, family_raw: str | None):
    """Strict brand + family when refs/entities are missing or inconsistent (unpriced listings)."""
    if not brand_raw or not family_raw:
        return None
    b = str(brand_raw).strip()
    f = str(family_raw).strip()
    if len(b) < 2 or len(f) < 2:
        return None
    return and_(
        brand_col.isnot(None),
        family_col.isnot(None),
        func.lower(brand_col) == b.lower(),
        func.lower(family_col) == f.lower(),
    )


async def find_open_buy_requests_for_offer(
    session: AsyncSession,
    offer: SellOffer,
    *,
    counterpart_message_not_before: datetime,
    limit: int = 50,
) -> list[BuyRequest]:
    filters = []
    if offer.watch_entity_id:
        filters.append(BuyRequest.watch_entity_id == offer.watch_entity_id)
    ref_clause = _reference_match_clause(BuyRequest.reference_raw, offer.reference_raw)
    if ref_clause is not None:
        filters.append(ref_clause)
    bf = _brand_family_clause(
        BuyRequest.brand_raw,
        BuyRequest.family_raw,
        offer.brand_raw,
        offer.family_raw,
    )
    if bf is not None:
        filters.append(bf)
    if not filters:
        return []
    buy_raw = aliased(RawMessage)
    stmt = (
        select(BuyRequest)
        .join(buy_raw, buy_raw.id == BuyRequest.raw_message_id)
        .where(BuyRequest.workspace_id == offer.workspace_id)
        .where(BuyRequest.status.in_(OPEN_REQUEST_STATUSES))
        .where(buy_raw.original_timestamp >= counterpart_message_not_before)
        .where(or_(*filters))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_active_sell_offers_for_request(
    session: AsyncSession,
    request: BuyRequest,
    *,
    counterpart_message_not_before: datetime,
    limit: int = 50,
) -> list[SellOffer]:
    filters = []
    if request.watch_entity_id:
        filters.append(SellOffer.watch_entity_id == request.watch_entity_id)
    ref_clause = _reference_match_clause(SellOffer.reference_raw, request.reference_raw)
    if ref_clause is not None:
        filters.append(ref_clause)
    bf = _brand_family_clause(
        SellOffer.brand_raw,
        SellOffer.family_raw,
        request.brand_raw,
        request.family_raw,
    )
    if bf is not None:
        filters.append(bf)
    if not filters:
        return []
    sell_raw = aliased(RawMessage)
    stmt = (
        select(SellOffer)
        .join(sell_raw, sell_raw.id == SellOffer.raw_message_id)
        .where(SellOffer.workspace_id == request.workspace_id)
        .where(SellOffer.status.in_(ACTIVE_OFFER_STATUSES))
        .where(sell_raw.original_timestamp >= counterpart_message_not_before)
        .where(or_(*filters))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
