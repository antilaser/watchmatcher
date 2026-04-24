from __future__ import annotations

import pytest

from app.parsing.rules import (
    extract_brand,
    extract_condition,
    extract_price_and_currency,
    extract_reference,
    extract_reference_prefer_caption,
    extract_set_completeness,
    extract_year,
    is_negotiable,
    split_calendar_year_reference,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("FS Rolex 126610LV", "Rolex"),
        ("AP Royal Oak 15500ST", "Audemars Piguet"),
        ("Looking for Patek 5711", "Patek Philippe"),
        ("продам ролекс батман", "Rolex"),
        ("Cartier Tank", "Cartier"),
        ("Random text", None),
    ],
)
def test_extract_brand(text, expected):
    assert extract_brand(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("FS Rolex 126610LV", "126610LV"),
        ("ref 5711/1A-010", "5711/1A-010"),
        ("Royal Oak 15500ST", "15500ST"),
        ("Patek 5167A-001", "5167A-001"),
        ("just text no number", None),
    ],
)
def test_extract_reference(text, expected):
    assert extract_reference(text) == expected


def test_extract_reference_skips_plain_calendar_year():
    assert extract_reference("Rolex 2022 full stickers") is None
    assert extract_reference("Rolex 2022 126334") == "126334"


def test_split_calendar_year_reference_moves_year_out_of_reference():
    assert split_calendar_year_reference("2024", None) == (None, 2024)
    assert split_calendar_year_reference("2024", 2022) == (None, 2022)
    assert split_calendar_year_reference("5711", None) == ("5711", None)


@pytest.mark.parametrize(
    "text,expected_year",
    [
        ("Card dated 24.04.2019 complete", 2019),
        ("Warranty 15-03-18", 2018),
        ("Rolex Datejust 2022 mint", 2022),
        ("1995 birth year piece", 1995),
        ("seen 01.01.2020 and 02.02.2021", 2020),
    ],
)
def test_extract_year(text, expected_year):
    assert extract_year(text) == expected_year


def test_extract_reference_prefer_caption():
    cap = "WTB - 218235"
    full = f"{cap}\nREF: 126334 NONE"
    assert extract_reference_prefer_caption(cap, full) == "218235"
    assert extract_reference_prefer_caption("", "Looking for 126334 full set") == "126334"
    assert extract_reference_prefer_caption(None, "Patek 5711/1A-010") == "5711/1A-010"


@pytest.mark.parametrize(
    "text,expected_price,expected_currency",
    [
        ("€13500 firm", 13500.0, "EUR"),
        ("13.5k EUR", 13500.0, "EUR"),
        ("$14,200", 14200.0, "USD"),
        ("asking 11750 USD", 11750.0, "USD"),
        ("price 27.5k", 27500.0, None),
        ("1.5k USD", 1500.0, "USD"),
        ("2.3M EUR", 2_300_000.0, "EUR"),
        ("$2.3m", 2_300_000.0, "USD"),
        ("18.5k евро", 18500.0, "EUR"),
        ("just text", None, None),
        ("Rolex 126500LN full stickers 22500", 22500.0, None),
        ("Rolex 126500LN story 22500", None, None),
    ],
)
def test_extract_price(text, expected_price, expected_currency):
    price, cur = extract_price_and_currency(text)
    if expected_price is None:
        assert price is None
    else:
        assert price == expected_price
    if expected_currency:
        assert cur == expected_currency


def test_condition_and_set():
    assert extract_condition("mint condition") == "mint"
    assert extract_condition("brand new BNIB") == "new"
    assert extract_set_completeness("full set 2023") == "full_set"
    assert extract_set_completeness("watch only") == "watch_only"


def test_negotiable():
    assert is_negotiable("€13500 OBO")
    assert is_negotiable("price 14k negotiable")
    assert not is_negotiable("price 14k firm")
