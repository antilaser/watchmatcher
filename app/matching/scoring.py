"""Match scoring formula (see SPEC §13.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScoreInputs:
    reference_score: float = 0.0
    brand_score: float = 0.0
    family_score: float = 0.0
    alias_score: float = 0.0
    parse_confidence: float = 0.0
    offer_created_at: datetime | None = None
    request_created_at: datetime | None = None


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def recency_score(offer_at: datetime | None, request_at: datetime | None) -> float:
    """Newer pairings score higher; max age considered = 30 days."""
    if not offer_at or not request_at:
        return 0.5
    now = datetime.now(timezone.utc)
    older = min(_ensure_aware(offer_at), _ensure_aware(request_at))
    age_days = (now - older).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    return max(0.0, 1.0 - min(age_days, 30.0) / 30.0)


def compute_match_score(s: ScoreInputs) -> float:
    rec = recency_score(s.offer_created_at, s.request_created_at)
    score = (
        0.35 * s.reference_score
        + 0.20 * s.brand_score
        + 0.15 * s.family_score
        + 0.10 * s.alias_score
        + 0.10 * s.parse_confidence
        + 0.10 * rec
    )
    return max(0.0, min(1.0, score))
