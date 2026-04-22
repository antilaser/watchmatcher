from __future__ import annotations

from decimal import Decimal

from app.matching.profit import ProfitInputs, calculate_profit


def _inputs(**kw):
    base = {
        "seller_price": Decimal("13500"),
        "buyer_price": Decimal("14000"),
        "seller_currency": "EUR",
        "buyer_currency": "EUR",
        "fx_rate": Decimal("1.0"),
        "shipping_cost": Decimal("80"),
        "fee_percent": Decimal("0.01"),
        "fixed_fee": Decimal("0"),
        "risk_buffer": Decimal("100"),
    }
    base.update(kw)
    return ProfitInputs(**base)


def test_simple_profit_same_currency():
    r = calculate_profit(_inputs())
    assert r.expected_profit == Decimal("180.00")
    assert not r.fx_applied


def test_missing_buyer_price_returns_none():
    r = calculate_profit(_inputs(buyer_price=None))
    assert r.expected_profit is None


def test_missing_seller_price_returns_none():
    r = calculate_profit(_inputs(seller_price=None))
    assert r.expected_profit is None


def test_negative_profit_supported():
    r = calculate_profit(_inputs(buyer_price=Decimal("13000")))
    assert r.expected_profit < 0


def test_fx_conversion_applied():
    r = calculate_profit(
        _inputs(seller_currency="USD", buyer_currency="EUR", fx_rate=Decimal("0.92"))
    )
    assert r.fx_applied
    assert r.seller_price_base == (Decimal("13500") * Decimal("0.92")).quantize(Decimal("0.01"))
