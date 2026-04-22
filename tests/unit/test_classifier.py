from __future__ import annotations

import pytest

from app.core.enums import MessageClassification
from app.parsing.classifier import classify


@pytest.mark.parametrize(
    "text,expected",
    [
        ("FS Rolex 126610LV €13500 full set", MessageClassification.SELL_OFFER),
        ("WTB Rolex Daytona around 30k EUR", MessageClassification.BUY_REQUEST),
        ("Looking for AP Royal Oak", MessageClassification.BUY_REQUEST),
        ("Available: Patek 5167A", MessageClassification.SELL_OFFER),
        ("Good morning everyone", MessageClassification.OTHER),
        ("продам Rolex Batman", MessageClassification.SELL_OFFER),
        ("куплю Rolex Pepsi", MessageClassification.BUY_REQUEST),
        ("", MessageClassification.OTHER),
    ],
)
def test_classify(text, expected):
    assert classify(text).classification == expected
