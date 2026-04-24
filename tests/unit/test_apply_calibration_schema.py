"""ApplyMatchCalibrationIn accepts horizon-only payloads (incl. days alias)."""

from app.schemas.calibration import ApplyMatchCalibrationIn


def test_horizon_only_match_candidate_max_age_days_key():
    m = ApplyMatchCalibrationIn.model_validate({"match_candidate_max_age_days": 11})
    assert m.match_candidate_max_age_days == 11
    assert m.reset_to_defaults is False
    assert m.use_suggestion is False
    assert m.unpriced_alert_min_match_confidence is None
    assert m.exact_reference_match_score_floor is None


def test_horizon_only_days_alias():
    m = ApplyMatchCalibrationIn.model_validate({"days": 9})
    assert m.match_candidate_max_age_days == 9


def test_empty_body_fails_gate_condition():
    m = ApplyMatchCalibrationIn.model_validate({})
    assert (
        m.reset_to_defaults
        or m.use_suggestion
        or m.unpriced_alert_min_match_confidence is not None
        or m.exact_reference_match_score_floor is not None
        or m.match_candidate_max_age_days is not None
    ) is False
