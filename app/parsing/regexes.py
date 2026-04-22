"""Compiled regexes for prices, references, years."""

from __future__ import annotations

import re

PRICE_REGEX = re.compile(
    r"""
    (?P<sym>[€$£¥₣])?\s*
    (?P<num>\d{1,3}(?:[.,\s]\d{3})+|\d{2,6}(?:[.,]\d{1,2})?)
    \s*
    (?P<suf>k|K|тыс|т\.р\.|т\.\sр\.)?
    \s*
    (?P<cur>EUR|USD|GBP|CHF|AED|JPY|RUB|euro|euros|eur|usd|gbp|chf|aed|jpy|rub|евро|долл|руб|€|\$|£|¥)?
    """,
    re.VERBOSE | re.IGNORECASE,
)

REFERENCE_REGEX = re.compile(
    r"\b(?:ref\.?\s*)?([A-Z]?\d{4,6}[A-Z]{0,4}(?:[-./]\d{1,4}[A-Z]{0,4}){0,3})\b",
    re.IGNORECASE,
)

YEAR_REGEX = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
