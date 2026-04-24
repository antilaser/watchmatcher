from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
import respx

from app.core.config import Settings
from app.matching.reporting_fx import _resolve_reporting_currency, build_reporting_amounts_for_profit


def test_resolve_auto_same_ccy():
    s = Settings(profit_reporting_currency="AUTO")
    assert _resolve_reporting_currency(s, "EUR", "EUR") == "EUR"
    assert _resolve_reporting_currency(s, "EUR", "GBP") == "USD"


def test_resolve_explicit():
    s = Settings(profit_reporting_currency="CHF")
    assert _resolve_reporting_currency(s, "EUR", "EUR") == "CHF"


@pytest.mark.asyncio
@respx.mock
async def test_build_reporting_with_xe_mock():
    respx.get(url__regex=r"https://xecdapi\.xe\.com/v1/convert_from\.json.*").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "from": "EUR",
                    "amount": 1,
                    "to": [{"quotecurrency": "USD", "mid": 1.1}],
                },
            ),
            httpx.Response(
                200,
                json={
                    "from": "GBP",
                    "amount": 1,
                    "to": [{"quotecurrency": "USD", "mid": 1.25}],
                },
            ),
        ]
    )

    s = Settings(
        profit_reporting_currency="USD",
        xe_account_id="acc",
        xe_api_key="key",
    )
    offer = SimpleNamespace(asking_price=Decimal("10000"), currency="EUR")
    request = SimpleNamespace(target_price=Decimal("9000"), currency="GBP")

    async with httpx.AsyncClient() as http:
        rep = await build_reporting_amounts_for_profit(offer=offer, request=request, settings=s, http=http)

    assert rep is not None
    assert rep.profit_currency == "USD"
    assert rep.seller == Decimal("11000.00")
    assert rep.buyer == Decimal("11250.00")
    assert rep.fx_meta["source"] == "xe.com"
