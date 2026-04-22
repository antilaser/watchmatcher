"""Review service — performs state transitions and writes audit trail."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    AlertStatus,
    BuyRequestStatus,
    MatchStatus,
    ReviewActionType,
    ReviewTargetType,
    SellOfferStatus,
    can_transition_buy_request,
    can_transition_match,
    can_transition_sell_offer,
)
from app.core.logging import get_logger
from app.models import Alert, BuyRequest, Match, ReviewAction, SellOffer

log = get_logger(__name__)


class ReviewError(ValueError):
    pass


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def perform(
        self,
        workspace_id: UUID,
        target_type: ReviewTargetType,
        target_id: UUID,
        action_type: ReviewActionType,
        actor_user_id: UUID | None = None,
        note: str | None = None,
    ) -> None:
        await self._dispatch(target_type, target_id, action_type)
        self.session.add(
            ReviewAction(
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                target_type=target_type,
                target_id=target_id,
                action_type=action_type,
                note=note,
            )
        )
        await self.session.flush()
        log.info(
            "review_action",
            target_type=target_type.value,
            target_id=str(target_id),
            action_type=action_type.value,
        )

    async def _dispatch(
        self,
        target_type: ReviewTargetType,
        target_id: UUID,
        action_type: ReviewActionType,
    ) -> None:
        match target_type:
            case ReviewTargetType.MATCH:
                await self._handle_match(target_id, action_type)
            case ReviewTargetType.SELL_OFFER:
                await self._handle_offer(target_id, action_type)
            case ReviewTargetType.BUY_REQUEST:
                await self._handle_request(target_id, action_type)
            case ReviewTargetType.ALERT:
                await self._handle_alert(target_id, action_type)
            case ReviewTargetType.PARSED_MESSAGE:
                await self._handle_parsed(target_id, action_type)

    async def _handle_match(self, match_id: UUID, action: ReviewActionType) -> None:
        m = (await self.session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
        if m is None:
            raise ReviewError("match not found")
        target = {
            ReviewActionType.APPROVE_MATCH: MatchStatus.APPROVED,
            ReviewActionType.REJECT_MATCH: MatchStatus.REJECTED,
            ReviewActionType.ARCHIVE: MatchStatus.REJECTED,
        }.get(action)
        if target is None:
            raise ReviewError(f"unsupported action {action} for MATCH")
        if not can_transition_match(m.status, target):
            raise ReviewError(f"invalid transition {m.status} -> {target}")
        m.status = target

        if target == MatchStatus.APPROVED:
            offer = (
                await self.session.execute(select(SellOffer).where(SellOffer.id == m.sell_offer_id))
            ).scalar_one()
            request = (
                await self.session.execute(select(BuyRequest).where(BuyRequest.id == m.buy_request_id))
            ).scalar_one()
            if can_transition_sell_offer(offer.status, SellOfferStatus.MATCHED):
                offer.status = SellOfferStatus.MATCHED
            if can_transition_buy_request(request.status, BuyRequestStatus.MATCHED):
                request.status = BuyRequestStatus.MATCHED

    async def _handle_offer(self, offer_id: UUID, action: ReviewActionType) -> None:
        offer = (
            await self.session.execute(select(SellOffer).where(SellOffer.id == offer_id))
        ).scalar_one_or_none()
        if offer is None:
            raise ReviewError("sell offer not found")
        target = {
            ReviewActionType.CLOSE_SELL_OFFER: SellOfferStatus.CLOSED,
            ReviewActionType.ARCHIVE: SellOfferStatus.ARCHIVED,
        }.get(action)
        if target is None:
            raise ReviewError(f"unsupported action {action} for SELL_OFFER")
        if not can_transition_sell_offer(offer.status, target):
            raise ReviewError(f"invalid transition {offer.status} -> {target}")
        offer.status = target
        offer.closed_at = datetime.now(timezone.utc)

    async def _handle_request(self, request_id: UUID, action: ReviewActionType) -> None:
        req = (
            await self.session.execute(select(BuyRequest).where(BuyRequest.id == request_id))
        ).scalar_one_or_none()
        if req is None:
            raise ReviewError("buy request not found")
        target = {
            ReviewActionType.CLOSE_BUY_REQUEST: BuyRequestStatus.CLOSED,
            ReviewActionType.ARCHIVE: BuyRequestStatus.ARCHIVED,
        }.get(action)
        if target is None:
            raise ReviewError(f"unsupported action {action} for BUY_REQUEST")
        if not can_transition_buy_request(req.status, target):
            raise ReviewError(f"invalid transition {req.status} -> {target}")
        req.status = target
        req.closed_at = datetime.now(timezone.utc)

    async def _handle_alert(self, alert_id: UUID, action: ReviewActionType) -> None:
        alert = (
            await self.session.execute(select(Alert).where(Alert.id == alert_id))
        ).scalar_one_or_none()
        if alert is None:
            raise ReviewError("alert not found")
        if action == ReviewActionType.SNOOZE_ALERT:
            return
        if action == ReviewActionType.ARCHIVE:
            alert.status = AlertStatus.ACKNOWLEDGED
            return
        raise ReviewError(f"unsupported action {action} for ALERT")

    async def _handle_parsed(self, parsed_id: UUID, action: ReviewActionType) -> None:
        if action != ReviewActionType.MARK_FALSE_PARSE:
            raise ReviewError(f"unsupported action {action} for PARSED_MESSAGE")
