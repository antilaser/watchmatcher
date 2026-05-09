from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.formatter import append_single_original_message_to_summary
from app.alerts.telegram import TelegramClient, stored_message_photo_path
from app.core.config import get_settings
from app.core.enums import AlertChannel, AlertStatus, AlertType
from app.models import Alert, BuyRequest, Group, ParsedMessage, RawMessage, SearchAlarm, SellOffer


def _contains(actual: str | None, wanted: str | None) -> bool:
    if not wanted:
        return True
    return bool(actual) and wanted.lower() in actual.lower()


def _price_matches(price: Decimal | None, alarm: SearchAlarm) -> bool:
    if alarm.price_min is None and alarm.price_max is None:
        return True
    if price is None:
        return False
    if alarm.price_min is not None and price < alarm.price_min:
        return False
    if alarm.price_max is not None and price > alarm.price_max:
        return False
    return True


def _year_matches(year: int | None, alarm: SearchAlarm) -> bool:
    if alarm.year_min is None and alarm.year_max is None:
        return True
    if year is None:
        return False
    if alarm.year_min is not None and year < alarm.year_min:
        return False
    if alarm.year_max is not None and year > alarm.year_max:
        return False
    return True


def _visual_matches(actual: str | None, wanted: str | None) -> bool:
    if not wanted:
        return True
    return bool(actual) and actual.strip().lower() == wanted.strip().lower()


class SearchAlarmService:
    def __init__(self, session: AsyncSession, telegram: TelegramClient | None = None) -> None:
        self.session = session
        self.settings = get_settings()
        self.telegram = telegram or TelegramClient()

    async def check_sell_offer(self, offer: SellOffer) -> list[Alert]:
        raw = await self.session.get(RawMessage, offer.raw_message_id)
        return await self._check(
            target_type="SELL",
            raw=raw,
            brand=offer.brand_raw,
            reference=offer.reference_raw,
            year=offer.manufacture_year,
            price=offer.asking_price,
            currency=offer.currency,
            visual_attrs={
                "dial_color": offer.dial_color,
                "bezel_color": offer.bezel_color,
                "case_material": offer.case_material,
                "bracelet_type": offer.bracelet_type,
            },
            title="Sell listing alarm",
            side_label="Seller",
        )

    async def check_buy_request(self, request: BuyRequest) -> list[Alert]:
        raw = await self.session.get(RawMessage, request.raw_message_id)
        parsed = await self.session.get(ParsedMessage, request.parsed_message_id)
        year = (parsed.extracted_json or {}).get("year") if parsed else None
        return await self._check(
            target_type="BUY",
            raw=raw,
            brand=request.brand_raw,
            reference=request.reference_raw,
            year=year if isinstance(year, int) else None,
            price=request.target_price,
            currency=request.currency,
            visual_attrs={
                "dial_color": request.dial_color,
                "bezel_color": request.bezel_color,
                "case_material": request.case_material,
                "bracelet_type": request.bracelet_type,
            },
            title="Buy request alarm",
            side_label="Buyer",
        )

    async def _check(
        self,
        *,
        target_type: str,
        raw: RawMessage | None,
        brand: str | None,
        reference: str | None,
        year: int | None,
        price: Decimal | None,
        currency: str | None,
        visual_attrs: dict[str, str | None],
        title: str,
        side_label: str,
    ) -> list[Alert]:
        if raw is None:
            return []
        alarms = (
            await self.session.execute(
                select(SearchAlarm)
                .where(SearchAlarm.workspace_id == raw.workspace_id)
                .where(SearchAlarm.is_active.is_(True))
                .where(SearchAlarm.target_type.in_((target_type, "ANY")))
            )
        ).scalars().all()
        out: list[Alert] = []
        for alarm in alarms:
            if not self._matches_alarm(alarm, brand, reference, year, price, currency, visual_attrs):
                continue
            if await self._already_alerted(alarm, raw):
                continue
            alert = await self._create_alert(
                alarm=alarm,
                raw=raw,
                target_type=target_type,
                title=title,
                side_label=side_label,
                brand=brand,
                reference=reference,
                year=year,
                price=price,
                currency=currency,
                visual_attrs=visual_attrs,
            )
            out.append(alert)
        return out

    def _matches_alarm(
        self,
        alarm: SearchAlarm,
        brand: str | None,
        reference: str | None,
        year: int | None,
        price: Decimal | None,
        currency: str | None,
        visual_attrs: dict[str, str | None],
    ) -> bool:
        if not _contains(brand, alarm.brand):
            return False
        if not _contains(reference, alarm.reference):
            return False
        if alarm.currency and (currency or "").upper() != alarm.currency.upper():
            return False
        if not _visual_matches(visual_attrs.get("dial_color"), alarm.dial_color):
            return False
        if not _visual_matches(visual_attrs.get("bezel_color"), alarm.bezel_color):
            return False
        if not _visual_matches(visual_attrs.get("case_material"), alarm.case_material):
            return False
        if not _visual_matches(visual_attrs.get("bracelet_type"), alarm.bracelet_type):
            return False
        return _year_matches(year, alarm) and _price_matches(price, alarm)

    async def _already_alerted(self, alarm: SearchAlarm, raw: RawMessage) -> bool:
        rows = (
            await self.session.execute(
                select(Alert)
                .where(Alert.raw_message_id == raw.id)
                .where(Alert.alert_type == AlertType.SEARCH_ALARM_MATCH)
            )
        ).scalars().all()
        return any((a.payload_json or {}).get("search_alarm_id") == str(alarm.id) for a in rows)

    async def _create_alert(
        self,
        *,
        alarm: SearchAlarm,
        raw: RawMessage,
        target_type: str,
        title: str,
        side_label: str,
        brand: str | None,
        reference: str | None,
        year: int | None,
        price: Decimal | None,
        currency: str | None,
        visual_attrs: dict[str, str | None],
    ) -> Alert:
        price_text = f"{price} {currency or ''}".strip() if price is not None else "no price"
        visual_text = ", ".join(
            f"{k.replace('_', ' ')}: {v}" for k, v in visual_attrs.items() if v
        ) or "unknown"
        headline = (
            f"SEARCH ALARM TRIGGERED\n"
            f"{title}: {alarm.name}\n"
            f"  type: {target_type}\n"
            f"  watch: {brand or 'Unknown brand'} {reference or 'Unknown ref'}\n"
            f"  year: {year or 'unknown'}\n"
            f"  price: {price_text}\n"
            f"  visual: {visual_text}"
        )
        group = await self.session.get(Group, raw.group_id)
        summary = append_single_original_message_to_summary(
            headline,
            side_label,
            (raw.text_body or "").strip(),
            sender_name=raw.sender_name,
            group_name=group.group_name if group else None,
            message_at=raw.original_timestamp,
        )
        alert = Alert(
            workspace_id=raw.workspace_id,
            raw_message_id=raw.id,
            alert_type=AlertType.SEARCH_ALARM_MATCH,
            channel=AlertChannel.DASHBOARD,
            payload_json={
                "summary": summary,
                "search_alarm_id": str(alarm.id),
                "search_alarm_name": alarm.name,
                "target_type": target_type,
                "visual_attributes": visual_attrs,
                "seller_message_text": raw.text_body if target_type == "SELL" else None,
                "buyer_message_text": raw.text_body if target_type == "BUY" else None,
            },
            status=AlertStatus.PENDING,
        )
        self.session.add(alert)
        alarm.last_triggered_at = datetime.now(timezone.utc)
        await self.session.flush()
        if self.telegram.enabled and self.settings.telegram_default_chat_id:
            sent = await self.telegram.send_message(
                chat_id=self.settings.telegram_default_chat_id,
                text=summary,
            )
            if sent:
                photo = stored_message_photo_path(raw.metadata_json)
                if photo:
                    await self.telegram.send_photo(
                        chat_id=self.settings.telegram_default_chat_id,
                        photo_path=photo,
                        caption=f"{side_label} picture",
                    )
                alert.channel = AlertChannel.TELEGRAM
                alert.status = AlertStatus.SENT
                alert.sent_at = datetime.now(timezone.utc)
        return alert
