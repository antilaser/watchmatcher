from __future__ import annotations

from app.core.config import Settings
from app.matching.calibration import (
    effective_match_candidate_max_age_days,
    suggest_calibration,
)
from app.models import Workspace


def test_suggest_insufficient_data():
    s = Settings()
    out = suggest_calibration(s, {}, {})
    assert out["unpriced_alert_min_match_confidence"] is None


def test_effective_match_candidate_max_age_days_workspace_override():
    s = Settings(match_candidate_max_age_days=7)
    ws = Workspace(name="w", settings_json={"match_calibration": {"match_candidate_max_age_days": 21}})
    assert effective_match_candidate_max_age_days(s, ws) == 21
    assert effective_match_candidate_max_age_days(s, None) == 7


def test_suggest_raises_threshold_when_many_bad():
    s = Settings(unpriced_alert_min_match_confidence=0.70, exact_reference_match_score_floor=0.86)
    counts = {"GOOD": 4, "BAD": 6}
    by_mt = {"FUZZY_REF": {"BAD": 5, "GOOD": 1}}
    out = suggest_calibration(s, counts, by_mt)
    assert out["unpriced_alert_min_match_confidence"] is not None
    assert out["unpriced_alert_min_match_confidence"] > 0.70
