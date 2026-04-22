"""Format alert payloads for human consumption."""

from __future__ import annotations

from app.models import BuyRequest, Match, SellOffer


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
    profit = (
        f"+{match.expected_profit}" if match.expected_profit is not None else "n/a"
    )
    return (
        f"{brand} {ref}\n"
        f"  seller: {offer.seller_name or '?'} -> {seller_price}\n"
        f"  buyer:  {request.buyer_name or '?'} -> {buyer_price}\n"
        f"  expected profit: {profit}\n"
        f"  match_confidence: {match.match_confidence:.2f} ({match.match_type})"
    )
