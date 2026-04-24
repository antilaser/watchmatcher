"""Format alert payloads for human consumption."""

from __future__ import annotations

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


def append_original_messages_to_summary(
    headline: str,
    seller_message: str | None,
    buyer_message: str | None,
) -> str:
    """Append labeled original chat texts for Telegram (truncated to fit API limits)."""
    parts: list[str] = [headline.rstrip()]
    sell = _clip_message(seller_message, _PER_SIDE_CAP)
    buy = _clip_message(buyer_message, _PER_SIDE_CAP)
    if sell:
        parts.append("\n\n--- Seller (original message) ---\n" + sell)
    if buy:
        parts.append("\n\n--- Buyer (original message) ---\n" + buy)
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
    return (
        f"{brand} {ref}\n"
        f"  seller: {offer.seller_name or '?'} -> {seller_price}\n"
        f"  buyer:  {request.buyer_name or '?'} -> {buyer_price}\n"
        f"  expected profit: {profit}{fx_block}\n"
        f"  match_confidence: {match.match_confidence:.2f} ({match.match_type})"
    )
