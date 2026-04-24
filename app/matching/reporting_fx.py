"""Convert seller/buyer legs to a single reporting currency via Xe (when configured)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import Settings
from app.fx.xe_client import xe_rate_via_cache
from app.models import BuyRequest, SellOffer


def _resolve_reporting_currency(settings: Settings, seller_ccy_raw: str, buyer_ccy_raw: str) -> str:
    """AUTO: use the shared leg currency when both sides agree; otherwise USD."""
    mode = (settings.profit_reporting_currency or "AUTO").strip().upper()
    sc = seller_ccy_raw.strip().upper()
    bc = buyer_ccy_raw.strip().upper()
    if mode == "AUTO":
        if sc and bc and sc == bc:
            return sc
        return "USD"
    return mode or "USD"


@dataclass
class ReportingProfitInputs:
    """Prices already expressed in ``profit_currency`` for ``calculate_profit``."""

    seller: Decimal
    buyer: Decimal
    profit_currency: str
    fx_meta: dict[str, Any]


def _same_leg_meta(ccy: str, reporting: str, amount: Decimal) -> dict[str, Any]:
    return {
        "from_currency": ccy,
        "to_currency": reporting,
        "amount_from": str(amount),
        "amount_to": str(amount),
        "implied_rate": "1",
        "provider": "none",
    }


async def build_reporting_amounts_for_profit(
    *,
    offer: SellOffer,
    request: BuyRequest,
    settings: Settings,
    http: httpx.AsyncClient,
) -> ReportingProfitInputs | None:
    """Return seller/buyer amounts in the resolved reporting currency.

    Returns ``None`` when conversion requires XE credentials or an XE call failed.
    """
    seller_p = offer.asking_price
    buyer_p = request.target_price
    if seller_p is None or buyer_p is None:
        return None

    sc_raw = (offer.currency or "").strip().upper()
    bc_raw = (request.currency or "").strip().upper()
    reporting = _resolve_reporting_currency(settings, sc_raw, bc_raw)
    seller_ccy = sc_raw or reporting
    buyer_ccy = bc_raw or reporting

    xe_id = (settings.xe_account_id or "").strip()
    xe_key = (settings.xe_api_key or "").strip()
    xe_ok = bool(xe_id and xe_key)

    async def leg(amount: Decimal, ccy: str) -> tuple[Decimal | None, dict[str, Any]]:
        if ccy == reporting:
            return amount, _same_leg_meta(ccy, reporting, amount)
        if not xe_ok:
            return None, {}
        meta = await xe_rate_via_cache(ccy, reporting, account_id=xe_id, api_key=xe_key, client=http)
        if meta is None:
            return None, {}
        out = (amount * meta.rate_implied).quantize(Decimal("0.01"))
        d = meta.to_dict()
        d["amount_from"] = str(amount)
        d["amount_to"] = str(out)
        return out, d

    s_amt, s_meta = await leg(seller_p, seller_ccy)
    b_amt, b_meta = await leg(buyer_p, buyer_ccy)
    if s_amt is None or b_amt is None:
        return None

    used_xe = any(
        m.get("provider") == "xe.com"
        for m in (s_meta, b_meta)
        if isinstance(m, dict)
    )
    fx_meta: dict[str, Any] = {
        "profit_reporting_currency": reporting,
        "source": "xe.com" if used_xe else "none",
        "seller_leg": s_meta,
        "buyer_leg": b_meta,
    }
    return ReportingProfitInputs(seller=s_amt, buyer=b_amt, profit_currency=reporting, fx_meta=fx_meta)
