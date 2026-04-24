from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MatchFeedbackStatsOut(BaseModel):
    since_days: int
    since_cutoff_utc: str
    counts: dict[str, int]
    by_match_type: dict[str, dict[str, int]]
    priced_breakdown: dict[str, int]
    suggested_calibration: dict[str, Any]
    current_calibration: dict[str, Any]


class MatchCandidateMaxAgeIn(BaseModel):
    """Update only the counterpart message age window (days)."""

    days: int = Field(ge=1, le=365)


class ApplyMatchCalibrationIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    use_suggestion: bool = False
    since_days: int = Field(default=30, ge=1, le=365)
    unpriced_alert_min_match_confidence: float | None = None
    exact_reference_match_score_floor: float | None = None
    # Counterpart search window by WhatsApp message time (original_timestamp), not ingest time.
    # "days" alias matches /workspace/match-candidate-max-age and UI fallbacks.
    match_candidate_max_age_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        validation_alias=AliasChoices("match_candidate_max_age_days", "days"),
    )
    reset_to_defaults: bool = False
