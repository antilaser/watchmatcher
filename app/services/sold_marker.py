from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AlertType, MatchStatus, SellOfferStatus
from app.core.logging import get_logger
from app.models import Alert, Match, RawMessage, SellOffer

log = get_logger(__name__)

_NEGATED_SOLD_RE = re.compile(r"\b(not|no|nicht|non)\s+sold\b", re.IGNORECASE)
_SOLD_RE = re.compile(
    r"\b("
    r"sold|sold\s+out|watch\s+sold|gone|"
    r"not\s+available|no\s+longer\s+available|unavailable|"
    r"withdrawn|off\s+market"
    r")\b",
    re.IGNORECASE,
)


def is_sold_marker(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if len(value) > 140:
        return False
    if _NEGATED_SOLD_RE.search(value):
        return False
    return bool(_SOLD_RE.search(value))


def quoted_message_id(raw: RawMessage) -> str | None:
    value = (raw.metadata_json or {}).get("quoted_message_id")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


async def close_quoted_sold_offer(session: AsyncSession, raw: RawMessage) -> bool:
    """Close the sell offer quoted by a short sold-marker message.

    Returns True when the raw message was handled and should not go through the
    normal listing parser.
    """
    if not is_sold_marker(raw.text_body):
        return False

    meta = dict(raw.metadata_json or {})
    meta["sold_marker_detected"] = True

    quoted_id = quoted_message_id(raw)
    if not quoted_id:
        meta["sold_marker_result"] = "no_quoted_message_id"
        raw.metadata_json = meta
        return True

    original = (
        await session.execute(
            select(RawMessage).where(
                RawMessage.group_id == raw.group_id,
                RawMessage.external_message_id == quoted_id,
            )
        )
    ).scalar_one_or_none()
    if original is None:
        meta["sold_marker_result"] = "quoted_message_not_found"
        meta["sold_marker_quoted_message_id"] = quoted_id
        raw.metadata_json = meta
        return True

    offer = (
        await session.execute(
            select(SellOffer).where(SellOffer.raw_message_id == original.id)
        )
    ).scalar_one_or_none()
    if offer is None:
        meta["sold_marker_result"] = "quoted_message_has_no_sell_offer"
        meta["sold_marker_quoted_raw_message_id"] = str(original.id)
        raw.metadata_json = meta
        return True

    now = datetime.now(timezone.utc)
    offer.status = SellOfferStatus.CLOSED
    offer.closed_at = now

    matches = (
        await session.execute(
            select(Match).where(
                Match.sell_offer_id == offer.id,
                Match.status != MatchStatus.EXPIRED,
            )
        )
    ).scalars().all()
    for match in matches:
        match.status = MatchStatus.EXPIRED
        match.reasoning_json = {
            **dict(match.reasoning_json or {}),
            "expired_reason": "seller_marked_sold",
            "sold_marker_raw_message_id": str(raw.id),
        }

    deleted_alerts = 0
    if matches:
        match_ids = [match.id for match in matches]
        alerts = (
            await session.execute(
                select(Alert).where(
                    Alert.match_id.in_(match_ids),
                    Alert.alert_type.in_(
                        (AlertType.PROFITABLE_MATCH, AlertType.UNPRICED_MATCH)
                    ),
                )
            )
        ).scalars().all()
        for alert in alerts:
            await session.delete(alert)
            deleted_alerts += 1

    search_alarm_alerts = (
        await session.execute(
            select(Alert).where(
                Alert.raw_message_id == original.id,
                Alert.alert_type == AlertType.SEARCH_ALARM_MATCH,
            )
        )
    ).scalars().all()
    for alert in search_alarm_alerts:
        await session.delete(alert)
        deleted_alerts += 1

    meta.update(
        {
            "sold_marker_result": "closed_sell_offer",
            "sold_marker_quoted_message_id": quoted_id,
            "sold_marker_quoted_raw_message_id": str(original.id),
            "sold_marker_sell_offer_id": str(offer.id),
            "sold_marker_expired_matches": len(matches),
            "sold_marker_deleted_alerts": deleted_alerts,
        }
    )
    raw.metadata_json = meta
    log.info(
        "sold_marker_closed_offer",
        raw_message_id=str(raw.id),
        sell_offer_id=str(offer.id),
        expired_matches=len(matches),
        deleted_alerts=deleted_alerts,
    )
    return True
