"""Alert service — creates Alert rows, suppresses duplicates, dispatches to channels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.formatter import append_original_messages_to_summary, format_match_summary
from app.alerts.telegram import TelegramClient, build_match_inline_keyboard
from app.core.config import get_settings
from app.core.enums import AlertChannel, AlertStatus, AlertType
from app.core.logging import get_logger
from app.matching.calibration import effective_unpriced_alert_min
from app.models import Alert, BuyRequest, Match, RawMessage, SellOffer, Workspace

log = get_logger(__name__)


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        telegram: TelegramClient | None = None,
    ) -> None:
        self.session = session
        self._telegram = telegram or TelegramClient()
        self._settings = get_settings()

    async def _classify_alert_type(self, match: Match) -> AlertType | None:
        min_conf = self._settings.default_min_match_confidence
        min_profit = Decimal(str(self._settings.default_min_profit_threshold))
        ws = (
            await self.session.execute(select(Workspace).where(Workspace.id == match.workspace_id))
        ).scalar_one_or_none()
        unpriced_min = effective_unpriced_alert_min(self._settings, ws)

        if match.expected_profit is not None:
            if match.match_confidence >= min_conf and match.expected_profit >= min_profit:
                return AlertType.PROFITABLE_MATCH
        else:
            if match.match_confidence >= unpriced_min:
                return AlertType.UNPRICED_MATCH
        return None

    async def maybe_create_for_match(self, match: Match) -> Alert | None:
        alert_type = await self._classify_alert_type(match)
        if alert_type is None:
            return None

        if await self._has_recent_duplicate(match):
            log.info("alert_duplicate_suppressed", match_id=str(match.id))
            return None

        offer = (
            await self.session.execute(select(SellOffer).where(SellOffer.id == match.sell_offer_id))
        ).scalar_one()
        request = (
            await self.session.execute(
                select(BuyRequest).where(BuyRequest.id == match.buy_request_id)
            )
        ).scalar_one()

        headline = format_match_summary(match, offer, request)

        sell_rm = await self.session.get(RawMessage, offer.raw_message_id)
        buy_rm = await self.session.get(RawMessage, request.raw_message_id)
        seller_message_text = (sell_rm.text_body or "").strip() if sell_rm else None
        buyer_message_text = (buy_rm.text_body or "").strip() if buy_rm else None
        if not seller_message_text:
            seller_message_text = None
        if not buyer_message_text:
            buyer_message_text = None

        telegram_text = append_original_messages_to_summary(
            headline, seller_message_text, buyer_message_text
        )

        alert = Alert(
            workspace_id=match.workspace_id,
            match_id=match.id,
            alert_type=alert_type,
            channel=AlertChannel.DASHBOARD,
            payload_json={
                "summary": headline,
                "seller_message_text": seller_message_text,
                "buyer_message_text": buyer_message_text,
                "match_id": str(match.id),
                "match_type": match.match_type.value,
                "match_confidence": float(match.match_confidence),
                "expected_profit": str(match.expected_profit)
                if match.expected_profit is not None
                else None,
                "seller_price": str(offer.asking_price) if offer.asking_price else None,
                "buyer_price": str(request.target_price) if request.target_price else None,
                "currency": offer.currency or request.currency,
            },
            status=AlertStatus.PENDING,
        )
        self.session.add(alert)
        await self.session.flush()

        if self._telegram.enabled and self._settings.telegram_default_chat_id:
            sent = await self._telegram.send_message(
                chat_id=self._settings.telegram_default_chat_id,
                text=telegram_text,
                reply_markup=build_match_inline_keyboard(str(match.id)),
            )
            if sent:
                alert.channel = AlertChannel.TELEGRAM
                alert.status = AlertStatus.SENT
                alert.sent_at = datetime.now(timezone.utc)

        log.info(
            "alert_created",
            alert_id=str(alert.id),
            type=alert_type.value,
            match_id=str(match.id),
        )
        return alert

    async def _has_recent_duplicate(self, match: Match) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._settings.alert_dedupe_hours)
        stmt = select(Alert).where(
            Alert.match_id == match.id,
            Alert.created_at >= cutoff,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
