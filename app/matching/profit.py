"""Profit and FX adjustment math. Uses Decimal everywhere for money."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ProfitInputs:
    seller_price: Decimal | None
    buyer_price: Decimal | None
    seller_currency: str | None
    buyer_currency: str | None
    fx_rate: Decimal | None
    shipping_cost: Decimal
    fee_percent: Decimal
    fixed_fee: Decimal
    risk_buffer: Decimal


@dataclass
class ProfitResult:
    expected_profit: Decimal | None
    seller_price_base: Decimal | None
    buyer_price_base: Decimal | None
    fx_applied: bool
    breakdown: dict


def calculate_profit(p: ProfitInputs) -> ProfitResult:
    if p.seller_price is None or p.buyer_price is None:
        return ProfitResult(
            expected_profit=None,
            seller_price_base=p.seller_price,
            buyer_price_base=p.buyer_price,
            fx_applied=False,
            breakdown={"reason": "missing_price"},
        )

    seller_base = p.seller_price
    buyer_base = p.buyer_price
    fx_applied = False
    if (
        p.seller_currency
        and p.buyer_currency
        and p.seller_currency != p.buyer_currency
        and p.fx_rate is not None
    ):
        seller_base = (p.seller_price * p.fx_rate).quantize(Decimal("0.01"))
        fx_applied = True

    fees = (buyer_base * p.fee_percent).quantize(Decimal("0.01")) + p.fixed_fee
    profit = buyer_base - seller_base - p.shipping_cost - fees - p.risk_buffer
    profit = profit.quantize(Decimal("0.01"))

    return ProfitResult(
        expected_profit=profit,
        seller_price_base=seller_base,
        buyer_price_base=buyer_base,
        fx_applied=fx_applied,
        breakdown={
            "seller_price": str(p.seller_price),
            "seller_price_base": str(seller_base),
            "buyer_price": str(p.buyer_price),
            "buyer_price_base": str(buyer_base),
            "shipping_cost": str(p.shipping_cost),
            "fees": str(fees),
            "risk_buffer": str(p.risk_buffer),
            "fx_applied": fx_applied,
            "fx_rate": str(p.fx_rate) if p.fx_rate else None,
        },
    )
