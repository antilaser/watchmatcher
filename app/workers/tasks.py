"""arq job functions. Each job opens its own session and is idempotent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.enums import BuyRequestStatus, SellOfferStatus
from app.core.logging import get_logger
from app.matching.service import MatchingService
from app.models import BuyRequest, SellOffer
from app.services.pipeline import PipelineService

log = get_logger(__name__)


async def process_raw_message_job(ctx: dict, raw_message_id: str) -> None:
    rid = UUID(raw_message_id)
    async with session_scope() as session:
        pipeline = PipelineService(session)
        await pipeline.process_raw_message(rid)


async def recompute_open_requests_job(ctx: dict) -> int:
    """Re-run matching for open buy requests and active sell offers (heals near-simultaneous ingest)."""
    n_buy = 0
    n_sell = 0
    async with session_scope() as session:
        matcher = MatchingService(session)
        buy_rows = (
            await session.execute(
                select(BuyRequest).where(
                    BuyRequest.status.in_(
                        (BuyRequestStatus.OPEN, BuyRequestStatus.OPEN_UNPRICED)
                    )
                )
            )
        ).scalars().all()
        for r in buy_rows:
            await matcher.match_for_new_request(r)
            n_buy += 1
        sell_rows = (
            await session.execute(
                select(SellOffer).where(SellOffer.status == SellOfferStatus.ACTIVE)
            )
        ).scalars().all()
        for o in sell_rows:
            await matcher.match_for_new_offer(o)
            n_sell += 1
    log.info("recompute_open_trades_done", buy_requests=n_buy, sell_offers=n_sell)
    return n_buy + n_sell


async def cleanup_expired_entities_job(ctx: dict) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    offer_cutoff = now - timedelta(days=settings.expire_offer_days)
    request_cutoff = now - timedelta(days=settings.expire_request_days)

    async with session_scope() as session:
        offer_res = await session.execute(
            update(SellOffer)
            .where(SellOffer.status == SellOfferStatus.ACTIVE)
            .where(SellOffer.created_at < offer_cutoff)
            .values(status=SellOfferStatus.EXPIRED, closed_at=now)
        )
        req_res = await session.execute(
            update(BuyRequest)
            .where(BuyRequest.status.in_((BuyRequestStatus.OPEN, BuyRequestStatus.OPEN_UNPRICED)))
            .where(BuyRequest.created_at < request_cutoff)
            .values(status=BuyRequestStatus.EXPIRED, closed_at=now)
        )
    out = {"offers_expired": offer_res.rowcount, "requests_expired": req_res.rowcount}
    log.info("cleanup_expired_done", **out)
    return out
