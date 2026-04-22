from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.matching.scoring import ScoreInputs, compute_match_score, recency_score


def test_recency_freshly_created_is_high():
    now = datetime.now(timezone.utc)
    assert recency_score(now, now) > 0.99


def test_recency_old_decays():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=20)
    assert recency_score(old, old) < 0.5


def test_compute_match_score_balanced():
    score = compute_match_score(
        ScoreInputs(
            reference_score=1.0,
            brand_score=1.0,
            family_score=1.0,
            alias_score=0.0,
            parse_confidence=0.9,
            offer_created_at=datetime.now(timezone.utc),
            request_created_at=datetime.now(timezone.utc),
        )
    )
    assert 0.85 <= score <= 1.0
