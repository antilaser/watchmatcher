from __future__ import annotations

import pytest

from app.parsing.rules import (
    extract_brand,
    extract_condition,
    extract_price_and_currency,
    extract_reference,
    extract_set_completeness,
    is_negotiable,
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


@pytest.mark.parametrize(
    "text,expected_price,expected_currency",
    [
        ("€13500 firm", 13500.0, "EUR"),
        ("13.5k EUR", 13500.0, "EUR"),
        ("$14,200", 14200.0, "USD"),
        ("asking 11750 USD", 11750.0, "USD"),
        ("price 27.5k", 27500.0, None),
        ("18.5k евро", 18500.0, "EUR"),
        ("just text", None, None),
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
