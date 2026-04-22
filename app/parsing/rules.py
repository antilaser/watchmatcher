"""Deterministic field extractors: brand, reference, condition, price, currency."""

from __future__ import annotations

import re

from app.parsing.dictionaries import (
    BRANDS,
    CONDITION_KEYWORDS,
    CURRENCY_SYMBOLS,
    NEGOTIABLE_KEYWORDS,
    SET_COMPLETENESS_KEYWORDS,
)
from app.parsing.regexes import PRICE_REGEX, REFERENCE_REGEX, YEAR_REGEX


def extract_brand(text: str) -> str | None:
    t = text.lower()
    for canonical, aliases in BRANDS.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", t):
                return canonical
    return None


def extract_reference(text: str) -> str | None:
    """Pick the first reference-looking token, normalized to uppercase."""
    for m in REFERENCE_REGEX.finditer(text):
        candidate = m.group(1).upper()
        if any(c.isdigit() for c in candidate) and len(candidate) >= 4:
            return candidate
    return None


def extract_year(text: str) -> int | None:
    m = YEAR_REGEX.search(text)
    return int(m.group(1)) if m else None


def extract_condition(text: str) -> str | None:
    t = text.lower()
    for canonical, terms in CONDITION_KEYWORDS.items():
        for term in terms:
            if term in t:
                return canonical
    return None


def extract_set_completeness(text: str) -> str | None:
    t = text.lower()
    for canonical, terms in SET_COMPLETENESS_KEYWORDS.items():
        for term in terms:
            if term in t:
                return canonical
    return None


def is_negotiable(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in NEGOTIABLE_KEYWORDS)


def _normalize_number(raw: str, suffix: str | None) -> float | None:
    """Turn a price-like string ('13,500.00', '12.5k', '1 200') into float."""
    if not raw:
        return None
    s = raw.strip().replace(" ", "")
    has_comma = "," in s
    has_dot = "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        if len(s.split(",")[-1]) == 3:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        value = float(s)
    except ValueError:
        return None

    if suffix and suffix.lower().startswith("k"):
        value *= 1000
    if suffix and suffix.lower().startswith(("тыс", "т.р")):
        value *= 1000
    return value


def extract_price_and_currency(text: str) -> tuple[float | None, str | None]:
    """Pick the most likely price.

    Strategy: only accept matches that are explicitly anchored by either
    a currency symbol/code OR a `k` / тыс suffix. This avoids picking up
    watch reference numbers (e.g. 126610) as prices.
    """
    candidates: list[tuple[int, float, str | None]] = []

    for m in PRICE_REGEX.finditer(text):
        raw_num = m.group("num")
        suffix = m.group("suf")
        sym = m.group("sym")
        cur = m.group("cur")

        value = _normalize_number(raw_num, suffix)
        if value is None or value <= 0:
            continue

        currency: str | None = None
        if sym and sym in CURRENCY_SYMBOLS:
            currency = CURRENCY_SYMBOLS[sym]
        elif cur:
            currency = CURRENCY_SYMBOLS.get(cur.lower())

        has_currency = currency is not None
        has_k_suffix = bool(
            suffix and suffix.lower().startswith(("k", "тыс", "т.р"))
        )

        if not has_currency and not has_k_suffix:
            continue

        priority = 2 if has_currency else 1
        candidates.append((priority, value, currency))

    if not candidates:
        return None, None

    top_priority = max(c[0] for c in candidates)
    best = max((c for c in candidates if c[0] == top_priority), key=lambda x: x[1])
    return best[1], best[2]
