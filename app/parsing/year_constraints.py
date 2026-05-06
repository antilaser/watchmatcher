"""Helpers for extracting watch year constraints from trade messages."""

from __future__ import annotations

import re

MIN_YEAR_REGEX = re.compile(r"(?<![0-9])(19\d{2}|20\d{2})\s*\+")


def extract_min_year(text: str | None) -> int | None:
    """Return 2022 for phrases like "2022+", meaning that year or newer."""
    if not text:
        return None
    match = MIN_YEAR_REGEX.search(text)
    return int(match.group(1)) if match else None
