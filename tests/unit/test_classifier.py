from __future__ import annotations

import pytest

from app.core.enums import MessageClassification
from app.parsing.classifier import classify
from app.parsing.year_constraints import extract_min_year


@pytest.mark.parametrize(
    "text,expected",
    [
        ("FS Rolex 126610LV €13500 full set", MessageClassification.SELL_OFFER),
        ("WTB Rolex Daytona around 30k EUR", MessageClassification.BUY_REQUEST),
        ("Looking for AP Royal Oak", MessageClassification.BUY_REQUEST),
        ("Available: Patek 5167A", MessageClassification.SELL_OFFER),
        ("Good morning everyone", MessageClassification.OTHER),
        ("need to buy 126334 for 10K usd", MessageClassification.BUY_REQUEST),
        ("Buy M228239 100k usd", MessageClassification.BUY_REQUEST),
        ("sell 126331", MessageClassification.SELL_OFFER),
        ("Ntq 126331 new card", MessageClassification.BUY_REQUEST),
        ("продам Rolex Batman", MessageClassification.SELL_OFFER),
        ("куплю Rolex Pepsi", MessageClassification.BUY_REQUEST),
        ("", MessageClassification.OTHER),
    ],
)
def test_classify(text, expected):
    assert classify(text).classification == expected


def test_image_caption_price_defaults_to_sell():
    r = classify("Daytona 116500LN full set £18500", has_image=True)
    assert r.classification == MessageClassification.SELL_OFFER
    assert "image_caption_price" in r.reason


def test_image_caption_bare_tail_amount_with_ref_is_sell():
    r = classify("Rolex 126500LN full stickers 22500", has_image=True)
    assert r.classification == MessageClassification.SELL_OFFER


def test_image_without_price_stays_other():
    r = classify("Nice piece today in the sun", has_image=True)
    assert r.classification == MessageClassification.OTHER


def test_text_only_price_no_keywords_stays_other():
    r = classify("Daytona 116500LN £18500", has_image=False)
    assert r.classification == MessageClassification.OTHER


def test_image_price_but_wtb_stays_buy():
    r = classify("WTB Pepsi GMT budget £12k", has_image=True)
    assert r.classification == MessageClassification.BUY_REQUEST


def test_dealer_listing_wire_and_retail_is_sell():
    text = (
        "Rolex Datejust 41 - diamond rhodium dial - 126334 - minus 1 - "
        "retail ready - 2018 - £8.7 wire"
    )
    assert classify(text, has_image=True).classification == MessageClassification.SELL_OFFER


def test_ntq_wire_listing_is_sell():
    r = classify("NTQ 20+ 5167A for wire pls", has_image=False)
    assert r.classification == MessageClassification.BUY_REQUEST


def test_wire_is_neutral_payment_method():
    assert classify("326933 for wire", has_image=False).classification == MessageClassification.OTHER
    assert classify("selling 326933 wire accepted", has_image=False).classification == MessageClassification.SELL_OFFER
    assert classify("need 326933 wire payment", has_image=False).classification == MessageClassification.BUY_REQUEST


def test_i_need_reference_for_wire_is_buy():
    r = classify("I need a 2022+ 326933 full set for wire please", has_image=False)
    assert r.classification == MessageClassification.BUY_REQUEST
    assert extract_min_year("I need a 2022+ 326933 full set for wire please") == 2022


def test_ntq_after_emoji_caption_is_buy():
    r = classify("📷 NTQ 5167a 2016-2020", has_image=True)
    assert r.classification == MessageClassification.BUY_REQUEST


def test_wtb_word_only_not_substring():
    assert classify("WTB 126334 full set", has_image=False).classification == MessageClassification.BUY_REQUEST
    assert classify("notwtb random", has_image=False).classification == MessageClassification.OTHER


def test_any_plus_reference_is_buy():
    assert classify("Any 116518LN Black diamond dial", has_image=False).classification == MessageClassification.BUY_REQUEST


def test_anyone_got_is_buy():
    assert classify("Anyone got exact please", has_image=False).classification == MessageClassification.BUY_REQUEST


def test_i_am_buying_is_buy():
    assert (
        classify("i am buying Rolex daytona 116503", has_image=False).classification
        == MessageClassification.BUY_REQUEST
    )


def test_lf_wlf_regex_buy():
    assert classify("LF 126610 full set", has_image=False).classification == MessageClassification.BUY_REQUEST
    assert classify("WLF 5711r", has_image=False).classification == MessageClassification.BUY_REQUEST


def test_ich_suche_and_recherche_buy():
    assert classify("ich suche eine 5711", has_image=False).classification == MessageClassification.BUY_REQUEST
    assert classify("recherche daytona", has_image=False).classification == MessageClassification.BUY_REQUEST


def test_verkaufe_is_sell_not_buy():
    assert classify("verkaufe Rolex 126610", has_image=False).classification == MessageClassification.SELL_OFFER


def test_sell_offer_phrase_is_sell():
    assert (
        classify("sell offer for 218235 5K", has_image=False).classification
        == MessageClassification.SELL_OFFER
    )


def test_image_only_vision_style_ref_without_price_is_sell():
    """Vision block may contain REF: lines and PRICE: NONE — still a listing photo."""
    text = "REF: 126610LV\nBRAND: Rolex\nPRICE: NONE\nNOTES: warranty card visible"
    assert classify(text, has_image=True).classification == MessageClassification.SELL_OFFER
