from __future__ import annotations

from app.normalization.similarity import reference_similarity, token_set_ratio


def test_reference_exact():
    assert reference_similarity("126610LV", "126610LV") == 1.0


def test_reference_case_insensitive():
    assert reference_similarity("126610lv", "126610LV") == 1.0


def test_reference_substring():
    assert reference_similarity("126610", "126610LV") >= 0.8


def test_token_set_partial():
    assert token_set_ratio("Submariner Date", "Sub Date") > 0.5
