"""Lightweight string similarity helpers."""

from __future__ import annotations

import re

from rapidfuzz import fuzz


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def token_set_ratio(a: str, b: str) -> float:
    return fuzz.token_set_ratio(normalize_text(a), normalize_text(b)) / 100.0


def reference_similarity(a: str, b: str) -> float:
    """Compare reference codes ignoring case/punctuation. Exact match -> 1.0."""
    aa = re.sub(r"[^A-Z0-9]", "", a.upper())
    bb = re.sub(r"[^A-Z0-9]", "", b.upper())
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    if aa in bb or bb in aa:
        return 0.85
    return fuzz.ratio(aa, bb) / 100.0
