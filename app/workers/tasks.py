"""arq job functions. Each job opens its own session and is idempotent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, or_, select, update

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.enums import BuyRequestStatus, EmbeddingObjectType, ReviewTargetType, SellOfferStatus
from app.core.logging import get_logger
from app.ingestion.image_store import delete_listing_image, delete_listing_images_older_than
from app.matching.service import MatchingService
from app.models import Alert, BuyRequest, Embedding, Match, ParsedMessage, RawMessage, ReviewAction, SellOffer
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
    message_cutoff = now - timedelta(days=settings.message_retention_days)

    async with session_scope() as session:
        old_raw_rows = (
            await session.execute(
                select(RawMessage).where(RawMessage.original_timestamp < message_cutoff)
            )
        ).scalars().all()
        old_raw_ids = [row.id for row in old_raw_rows]
        images_deleted = 0
        for raw in old_raw_rows:
            if delete_listing_image(dict(raw.metadata_json or {})):
                images_deleted += 1
        orphan_images_deleted = delete_listing_images_older_than(settings.message_retention_days)

        alerts_deleted = 0
        review_actions_deleted = 0
        messages_deleted = 0
        if old_raw_ids:
            old_parsed_ids = (
                await session.execute(
                    select(ParsedMessage.id).where(ParsedMessage.raw_message_id.in_(old_raw_ids))
                )
            ).scalars().all()
            old_offer_ids = (
                await session.execute(
                    select(SellOffer.id).where(SellOffer.raw_message_id.in_(old_raw_ids))
                )
            ).scalars().all()
            old_request_ids = (
                await session.execute(
                    select(BuyRequest.id).where(BuyRequest.raw_message_id.in_(old_raw_ids))
                )
            ).scalars().all()
            match_filters = []
            if old_offer_ids:
                match_filters.append(Match.sell_offer_id.in_(old_offer_ids))
            if old_request_ids:
                match_filters.append(Match.buy_request_id.in_(old_request_ids))
            match_ids = []
            if match_filters:
                match_ids = (
                    await session.execute(select(Match.id).where(or_(*match_filters)))
                ).scalars().all()

            alert_filters = [Alert.raw_message_id.in_(old_raw_ids)]
            if match_ids:
                alert_filters.append(Alert.match_id.in_(match_ids))
            old_alert_ids = (
                await session.execute(select(Alert.id).where(or_(*alert_filters)))
            ).scalars().all()
            alert_res = await session.execute(delete(Alert).where(or_(*alert_filters)))
            alerts_deleted = alert_res.rowcount or 0

            review_filters = []
            target_sets = (
                (ReviewTargetType.PARSED_MESSAGE, old_parsed_ids),
                (ReviewTargetType.SELL_OFFER, old_offer_ids),
                (ReviewTargetType.BUY_REQUEST, old_request_ids),
                (ReviewTargetType.MATCH, match_ids),
                (ReviewTargetType.ALERT, old_alert_ids),
            )
            for target_type, ids in target_sets:
                if ids:
                    review_filters.append(
                        (ReviewAction.target_type == target_type.value)
                        & (ReviewAction.target_id.in_(ids))
                    )
            if review_filters:
                review_res = await session.execute(delete(ReviewAction).where(or_(*review_filters)))
                review_actions_deleted = review_res.rowcount or 0

            embedding_filters = []
            embedding_sets = (
                (EmbeddingObjectType.RAW_MESSAGE, old_raw_ids),
                (EmbeddingObjectType.PARSED_MESSAGE, old_parsed_ids),
                (EmbeddingObjectType.SELL_OFFER, old_offer_ids),
                (EmbeddingObjectType.BUY_REQUEST, old_request_ids),
            )
            for object_type, ids in embedding_sets:
                if ids:
                    embedding_filters.append(
                        (Embedding.object_type == object_type.value)
                        & (Embedding.object_id.in_(ids))
                    )
            embeddings_deleted = 0
            if embedding_filters:
                embedding_res = await session.execute(delete(Embedding).where(or_(*embedding_filters)))
                embeddings_deleted = embedding_res.rowcount or 0

            raw_res = await session.execute(delete(RawMessage).where(RawMessage.id.in_(old_raw_ids)))
            messages_deleted = raw_res.rowcount or 0
        else:
            embeddings_deleted = 0

        # Fallback for any legacy sell offers not attached to raw messages.
        old_legacy_offer_ids = (
            await session.execute(
                select(SellOffer.id)
                .where(SellOffer.created_at < message_cutoff)
                .where(~SellOffer.raw_message_id.in_(old_raw_ids) if old_raw_ids else True)
            )
        ).scalars().all()
        legacy_listings_deleted = 0
        if old_legacy_offer_ids:
            legacy_match_ids = (
                await session.execute(
                    select(Match.id).where(Match.sell_offer_id.in_(old_legacy_offer_ids))
                )
            ).scalars().all()
            if legacy_match_ids:
                await session.execute(delete(Alert).where(Alert.match_id.in_(legacy_match_ids)))
            legacy_res = await session.execute(delete(SellOffer).where(SellOffer.id.in_(old_legacy_offer_ids)))
            legacy_listings_deleted = legacy_res.rowcount or 0

        stale_alert_res = await session.execute(delete(Alert).where(Alert.created_at < message_cutoff))
        stale_review_res = await session.execute(delete(ReviewAction).where(ReviewAction.created_at < message_cutoff))
        alerts_deleted += stale_alert_res.rowcount or 0
        review_actions_deleted += stale_review_res.rowcount or 0

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
    out = {
        "offers_expired": offer_res.rowcount,
        "requests_expired": req_res.rowcount,
        "images_deleted": images_deleted,
        "orphan_images_deleted": orphan_images_deleted,
        "messages_deleted": messages_deleted,
        "legacy_listings_deleted": legacy_listings_deleted,
        "alerts_deleted": alerts_deleted,
        "review_actions_deleted": review_actions_deleted,
        "embeddings_deleted": embeddings_deleted,
        "message_retention_days": settings.message_retention_days,
    }
    log.info("cleanup_expired_done", **out)
    return out
