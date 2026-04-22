"""Candidate search: find counterparts for a new offer or request."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BuyRequestStatus, SellOfferStatus
from app.models import BuyRequest, SellOffer


ACTIVE_OFFER_STATUSES = (SellOfferStatus.ACTIVE,)
OPEN_REQUEST_STATUSES = (BuyRequestStatus.OPEN, BuyRequestStatus.OPEN_UNPRICED)


async def find_open_buy_requests_for_offer(
    session: AsyncSession,
    offer: SellOffer,
    limit: int = 50,
) -> list[BuyRequest]:
    filters = []
    if offer.watch_entity_id:
        filters.append(BuyRequest.watch_entity_id == offer.watch_entity_id)
    if offer.reference_raw:
        filters.append(BuyRequest.reference_raw.ilike(offer.reference_raw))
    if not filters:
        return []
    stmt = (
        select(BuyRequest)
        .where(BuyRequest.workspace_id == offer.workspace_id)
        .where(BuyRequest.status.in_(OPEN_REQUEST_STATUSES))
        .where(or_(*filters))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def find_active_sell_offers_for_request(
    session: AsyncSession,
    request: BuyRequest,
    limit: int = 50,
) -> list[SellOffer]:
    filters = []
    if request.watch_entity_id:
        filters.append(SellOffer.watch_entity_id == request.watch_entity_id)
    if request.reference_raw:
        filters.append(SellOffer.reference_raw.ilike(request.reference_raw))
    if not filters:
        return []
    stmt = (
        select(SellOffer)
        .where(SellOffer.workspace_id == request.workspace_id)
        .where(SellOffer.status.in_(ACTIVE_OFFER_STATUSES))
        .where(or_(*filters))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
