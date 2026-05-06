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

_REFERENCE_YEAR_EXCEPTIONS = {"1908"}


def extract_brand(text: str) -> str | None:
    t = text.lower()
    for canonical, aliases in BRANDS.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", t):
                return canonical
    return None


def _is_plain_calendar_year_token(candidate: str) -> bool:
    """4-digit 19xx/20xx tokens are manufacturing or card dates, not model references."""
    if candidate in _REFERENCE_YEAR_EXCEPTIONS:
        return False
    if len(candidate) != 4 or not candidate.isdigit():
        return False
    val = int(candidate)
    return 1900 <= val <= 2099


def split_calendar_year_reference(
    reference: str | None,
    year: int | None,
) -> tuple[str | None, int | None]:
    """Move a plain 19xx/20xx reference token into the year field."""
    if reference is None:
        return None, year

    ref = reference.strip()
    if not ref:
        return None, year

    if _is_plain_calendar_year_token(ref):
        return None, year if year is not None else int(ref)

    return ref, year


def extract_reference(text: str) -> str | None:
    """Pick the first reference-looking token, normalized to uppercase."""
    for m in REFERENCE_REGEX.finditer(text):
        candidate = m.group(1).upper()
        if any(c.isdigit() for c in candidate) and len(candidate) >= 4:
            if _is_plain_calendar_year_token(candidate):
                continue
            return candidate
    return None


def extract_reference_prefer_caption(caption: str | None, full_text: str) -> str | None:
    """Prefer a reference from the user caption; fall back to the full parse text (e.g. vision block)."""
    cap = (caption or "").strip()
    if cap:
        ref = extract_reference(cap)
        if ref:
            return ref
    return extract_reference(full_text)


_EU_NUMERIC_DATE = re.compile(
    r"(?<![0-9])(\d{1,2})[./\-](\d{1,2})[./\-](\d{2}|\d{4})(?![0-9])",
    re.IGNORECASE,
)
_MONTH_YEAR_DATE = re.compile(
    r"(?<![0-9])(\d{1,2})[./\-](\d{2}|\d{4})(?![0-9])",
    re.IGNORECASE,
)


def _expand_two_digit_year(y: int) -> int:
    if y >= 100:
        return y
    if y <= 39:
        return 2000 + y
    return 1900 + y


def _year_from_eu_dates(text: str) -> int | None:
    """DD.MM.YYYY, DD/MM/YY, etc. (day-first, common on EU warranty cards)."""
    hits: list[tuple[int, int]] = []
    for m in _EU_NUMERIC_DATE.finditer(text):
        d, mo = int(m.group(1)), int(m.group(2))
        y_raw = m.group(3)
        yi = int(y_raw)
        year_full = _expand_two_digit_year(yi) if len(y_raw) == 2 else yi
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            continue
        if not (1900 <= year_full <= 2099):
            continue
        hits.append((m.start(), year_full))
    if not hits:
        return None
    hits.sort(key=lambda h: h[0])
    return hits[0][1]


def _year_from_month_year_dates(text: str) -> int | None:
    """MM/YY, MM.YYYY, etc. on warranty cards. Example: 04/26 -> 2026."""
    hits: list[tuple[int, int]] = []
    eu_date_spans = [m.span() for m in _EU_NUMERIC_DATE.finditer(text)]
    for m in _MONTH_YEAR_DATE.finditer(text):
        if any(start <= m.start() and m.end() <= end for start, end in eu_date_spans):
            continue
        month = int(m.group(1))
        y_raw = m.group(2)
        year_full = _expand_two_digit_year(int(y_raw)) if len(y_raw) == 2 else int(y_raw)
        if not (1 <= month <= 12):
            continue
        if not (1900 <= year_full <= 2099):
            continue
        hits.append((m.start(), year_full))
    if not hits:
        return None
    hits.sort(key=lambda h: h[0])
    return hits[0][1]


def extract_year(text: str) -> int | None:
    """Manufacturing or card year: prefer explicit EU-style dates, then standalone 19xx/20xx."""
    y = _year_from_eu_dates(text)
    if y is not None:
        return y
    y = _year_from_month_year_dates(text)
    if y is not None:
        return y
    for m in YEAR_REGEX.finditer(text):
        candidate = m.group(1)
        if candidate in _REFERENCE_YEAR_EXCEPTIONS:
            continue
        return int(candidate)
    return None


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


# Dealer captions often end with a bare integer ("… full stickers 22500") with no currency.
_LISTING_TAIL_CONTEXT = re.compile(
    r"(?i)\b("
    r"stickers?|full\s+stickers|full\s+set|fullset|complete|box|papers?|"
    r"minus|nwcht|naked|head\s+only|retail|asking|firm|net"
    r")\b"
)


def _extract_dealer_tail_amount(text: str) -> float | None:
    """Last 4–6 digit token as price when a ref exists and caption looks like a listing."""
    stripped = text.strip()
    if not extract_reference(stripped):
        return None
    if not _LISTING_TAIL_CONTEXT.search(stripped):
        return None
    m = re.search(r"(?:\s|^)(\d{4,6})\s*$", stripped)
    if not m:
        return None
    raw = m.group(1)
    value = float(int(raw))
    if value < 1500:
        return None
    if len(raw) == 4 and 1990 <= value <= 2040:
        return None
    return value


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

    if not suffix:
        return value
    sl = suffix.lower()
    if sl.startswith("k") or sl.startswith("тыс") or sl.startswith("т.р"):
        value *= 1000
    elif sl.startswith("m"):
        value *= 1_000_000
    return value


def extract_price_and_currency(text: str) -> tuple[float | None, str | None]:
    """Pick the most likely price.

    Strategy: only accept matches that are explicitly anchored by either
    a currency symbol/code OR a short scale suffix (`k`/`m` / тыс). This avoids
    picking up bare watch reference numbers (e.g. 126610) as prices.
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
        suf = (suffix or "").lower()
        has_scale_suffix = bool(
            suffix
            and (
                suf.startswith("k")
                or suf.startswith("m")
                or suf.startswith("тыс")
                or suf.startswith("т.р")
            )
        )

        if not has_currency and not has_scale_suffix:
            continue

        priority = 2 if has_currency else 1
        candidates.append((priority, value, currency))

    if not candidates:
        tail = _extract_dealer_tail_amount(text)
        if tail is not None:
            return tail, None
        return None, None

    top_priority = max(c[0] for c in candidates)
    best = max((c for c in candidates if c[0] == top_priority), key=lambda x: x[1])
    return best[1], best[2]
