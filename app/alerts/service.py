"""Alert service — creates Alert rows, suppresses duplicates, dispatches to channels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.formatter import append_original_messages_to_summary, format_match_summary
from app.alerts.telegram import TelegramClient, stored_message_photo_path
from app.core.config import get_settings
from app.core.enums import AlertChannel, AlertStatus, AlertType
from app.core.logging import get_logger
from app.matching.calibration import effective_unpriced_alert_min
from app.models import Alert, BuyRequest, Group, Match, RawMessage, SellOffer, Workspace

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
        sell_group = await self.session.get(Group, sell_rm.group_id) if sell_rm else None
        buy_group = await self.session.get(Group, buy_rm.group_id) if buy_rm else None
        seller_message_text = (sell_rm.text_body or "").strip() if sell_rm else None
        buyer_message_text = (buy_rm.text_body or "").strip() if buy_rm else None
        if not seller_message_text:
            seller_message_text = None
        if not buyer_message_text:
            buyer_message_text = None

        telegram_text = append_original_messages_to_summary(
            "REGULAR MATCH ALERT\n" + headline,
            seller_message_text,
            buyer_message_text,
            seller_name=sell_rm.sender_name if sell_rm else None,
            seller_group=sell_group.group_name if sell_group else None,
            seller_time=sell_rm.original_timestamp if sell_rm else None,
            buyer_name=buy_rm.sender_name if buy_rm else None,
            buyer_group=buy_group.group_name if buy_group else None,
            buyer_time=buy_rm.original_timestamp if buy_rm else None,
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
                "seller_message_at": sell_rm.original_timestamp.isoformat() if sell_rm else None,
                "buyer_message_at": buy_rm.original_timestamp.isoformat() if buy_rm else None,
                "match_id": str(match.id),
                "match_type": match.match_type.value,
                "match_confidence": float(match.match_confidence),
                "expected_profit": str(match.expected_profit)
                if match.expected_profit is not None
                else None,
                "seller_price": str(offer.asking_price) if offer.asking_price else None,
                "buyer_price": str(request.target_price) if request.target_price else None,
                "currency": offer.currency or request.currency,
                "visual_attributes": {
                    "seller": {
                        "dial_color": offer.dial_color,
                        "dial_variant": offer.dial_variant,
                        "bezel_color": offer.bezel_color,
                        "case_material": offer.case_material,
                        "bracelet_type": offer.bracelet_type,
                    },
                    "buyer": {
                        "dial_color": request.dial_color,
                        "dial_variant": request.dial_variant,
                        "bezel_color": request.bezel_color,
                        "case_material": request.case_material,
                        "bracelet_type": request.bracelet_type,
                    },
                    "score_adjustment": (match.reasoning_json or {}).get("visual_score_adjustment"),
                },
            },
            status=AlertStatus.PENDING,
        )
        self.session.add(alert)
        await self.session.flush()

        if self._telegram.enabled and self._settings.telegram_default_chat_id:
            sent = await self._telegram.send_message(
                chat_id=self._settings.telegram_default_chat_id,
                text=telegram_text,
            )
            if sent:
                sell_photo = stored_message_photo_path(sell_rm.metadata_json if sell_rm else None)
                buy_photo = stored_message_photo_path(buy_rm.metadata_json if buy_rm else None)
                if sell_photo:
                    await self._telegram.send_photo(
                        chat_id=self._settings.telegram_default_chat_id,
                        photo_path=sell_photo,
                        caption="Seller picture",
                    )
                if buy_photo and buy_photo != sell_photo:
                    await self._telegram.send_photo(
                        chat_id=self._settings.telegram_default_chat_id,
                        photo_path=buy_photo,
                        caption="Buyer picture",
                    )
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
