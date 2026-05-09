"""Format alert payloads for human consumption."""

from __future__ import annotations

from datetime import datetime

from app.models import BuyRequest, Match, SellOffer

# Telegram hard limit is 4096; leave margin for reply markup / encoding.
_TELEGRAM_SAFE_MAX = 3900
_PER_SIDE_CAP = 1700


def _clip_message(text: str | None, cap: int) -> str | None:
    if not text:
        return None
    t = text.strip()
    if not t:
        return None
    if len(t) <= cap:
        return t
    return t[: cap - 1] + "…"


def _fmt_time(value: datetime | None) -> str:
    if value is None:
        return "unknown time"
    return value.strftime("%Y-%m-%d %H:%M %Z").strip() or value.isoformat()


def _message_section(
    label: str,
    message: str | None,
    *,
    sender_name: str | None = None,
    group_name: str | None = None,
    message_at: datetime | None = None,
) -> str | None:
    clipped = _clip_message(message, _PER_SIDE_CAP)
    if not clipped:
        return None
    sender = sender_name or "unknown sender"
    group = group_name or "unknown group"
    return (
        f"\n\n{label}\n"
        f"posted by: {sender}\n"
        f"group: {group}\n"
        f"time: {_fmt_time(message_at)}\n"
        f"message:\n{clipped}"
    )


def append_original_messages_to_summary(
    headline: str,
    seller_message: str | None,
    buyer_message: str | None,
    *,
    seller_name: str | None = None,
    seller_group: str | None = None,
    seller_time: datetime | None = None,
    buyer_name: str | None = None,
    buyer_group: str | None = None,
    buyer_time: datetime | None = None,
) -> str:
    """Append labeled original chat texts for Telegram (truncated to fit API limits)."""
    title = headline.splitlines()[0] if headline.strip() else "MATCH ALERT"
    details = "\n".join(headline.splitlines()[1:]).strip()
    parts: list[str] = [title.rstrip()]
    sell = _message_section(
        "SELLER ORIGINAL MESSAGE",
        seller_message,
        sender_name=seller_name,
        group_name=seller_group,
        message_at=seller_time,
    )
    buy = _message_section(
        "BUYER ORIGINAL MESSAGE",
        buyer_message,
        sender_name=buyer_name,
        group_name=buyer_group,
        message_at=buyer_time,
    )
    if sell:
        parts.append(sell)
    if buy:
        parts.append(buy)
    if details:
        parts.append(f"\n\nMATCH DETAILS\n{details}")
    out = "".join(parts)
    if len(out) <= _TELEGRAM_SAFE_MAX:
        return out
    return out[: _TELEGRAM_SAFE_MAX - 1] + "…"


def append_single_original_message_to_summary(
    headline: str,
    label: str,
    message: str | None,
    *,
    sender_name: str | None = None,
    group_name: str | None = None,
    message_at: datetime | None = None,
) -> str:
    parts = [headline.rstrip()]
    section = _message_section(
        f"{label.upper()} ORIGINAL MESSAGE",
        message,
        sender_name=sender_name,
        group_name=group_name,
        message_at=message_at,
    )
    if section:
        parts.append(section)
    out = "".join(parts)
    if len(out) <= _TELEGRAM_SAFE_MAX:
        return out
    return out[: _TELEGRAM_SAFE_MAX - 1] + "…"


def format_match_summary(
    match: Match,
    offer: SellOffer,
    request: BuyRequest,
) -> str:
    brand = offer.brand_raw or request.brand_raw or "Unknown brand"
    ref = offer.reference_raw or request.reference_raw or "Unknown ref"
    seller_price = (
        f"{offer.asking_price} {offer.currency}" if offer.asking_price else "no price"
    )
    buyer_price = (
        f"{request.target_price} {request.currency}" if request.target_price else "no price"
    )
    pb = match.reasoning_json.get("profit_breakdown") if match.reasoning_json else None
    fx = pb.get("fx_conversion") if isinstance(pb, dict) else None
    cur_note = ""
    fx_block = ""
    if isinstance(fx, dict):
        cur = fx.get("profit_reporting_currency") or ""
        if cur:
            cur_note = f" ({cur})"
        sl = fx.get("seller_leg") or {}
        bl = fx.get("buyer_leg") or {}
        src = fx.get("source") or "xe.com"
        if sl.get("from_currency") and bl.get("from_currency"):
            fx_block = (
                f"\n  FX ({src}): profit shown in {cur}\n"
                f"    seller: {sl.get('amount_from')} {sl.get('from_currency')} -> {sl.get('amount_to')} {sl.get('to_currency')} (×{sl.get('implied_rate')})\n"
                f"    buyer:  {bl.get('amount_from')} {bl.get('from_currency')} -> {bl.get('amount_to')} {bl.get('to_currency')} (×{bl.get('implied_rate')})"
            )
    profit = (
        f"+{match.expected_profit}{cur_note}" if match.expected_profit is not None else "n/a"
    )
    visual_bits = []
    if offer.dial_color or request.dial_color:
        visual_bits.append(f"dial seller/buyer: {offer.dial_color or '?'} / {request.dial_color or '?'}")
    if offer.dial_variant or request.dial_variant:
        visual_bits.append(f"dial variant seller/buyer: {offer.dial_variant or '?'} / {request.dial_variant or '?'}")
    if offer.bezel_color or request.bezel_color:
        visual_bits.append(f"bezel seller/buyer: {offer.bezel_color or '?'} / {request.bezel_color or '?'}")
    if offer.case_material or request.case_material:
        visual_bits.append(f"case seller/buyer: {offer.case_material or '?'} / {request.case_material or '?'}")
    visual_line = f"\n  visual: {'; '.join(visual_bits)}" if visual_bits else ""
    return (
        f"{brand} {ref}\n"
        f"  seller: {offer.seller_name or '?'} -> {seller_price}\n"
        f"  buyer:  {request.buyer_name or '?'} -> {buyer_price}\n"
        f"  expected profit: {profit}{fx_block}\n"
        f"  match_confidence: {match.match_confidence:.2f} ({match.match_type})"
        f"{visual_line}"
    )
