"""Workspace-level match calibration from human feedback (GOOD/BAD labels)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import HumanMatchFeedback, MatchType
from app.models import Match, Workspace

MATCH_CALIBRATION_KEY = "match_calibration"


def calibration_from_workspace(workspace: Workspace | None) -> dict[str, Any]:
    if workspace is None or not workspace.settings_json:
        return {}
    raw = (workspace.settings_json or {}).get(MATCH_CALIBRATION_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def effective_unpriced_alert_min(settings: Settings, workspace: Workspace | None) -> float:
    cal = calibration_from_workspace(workspace)
    v = cal.get("unpriced_alert_min_match_confidence")
    if v is not None and isinstance(v, (int, float)):
        return float(max(0.35, min(0.99, float(v))))
    return float(settings.unpriced_alert_min_match_confidence)


def effective_exact_reference_floor(settings: Settings, workspace: Workspace | None) -> float:
    cal = calibration_from_workspace(workspace)
    v = cal.get("exact_reference_match_score_floor")
    if v is not None and isinstance(v, (int, float)):
        return float(max(0.5, min(0.99, float(v))))
    return float(settings.exact_reference_match_score_floor)


def effective_match_candidate_max_age_days(settings: Settings, workspace: Workspace | None) -> int:
    """How far back (by message sent time) counterpart buy/sell rows may be for matching."""
    cal = calibration_from_workspace(workspace)
    v = cal.get("match_candidate_max_age_days")
    if v is not None and isinstance(v, (int, float)):
        return int(max(1, min(365, int(v))))
    return int(max(1, min(365, settings.match_candidate_max_age_days)))


def suggest_calibration(
    settings: Settings,
    counts: dict[str, int],
    by_match_type: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Heuristic suggestion from labeled pairs; returns None values if not enough data."""
    good = int(counts.get(HumanMatchFeedback.GOOD.value, 0) or 0)
    bad = int(counts.get(HumanMatchFeedback.BAD.value, 0) or 0)
    total = good + bad
    base_u = float(settings.unpriced_alert_min_match_confidence)
    base_f = float(settings.exact_reference_match_score_floor)

    if total < 6:
        return {
            "unpriced_alert_min_match_confidence": None,
            "exact_reference_match_score_floor": None,
            "rationale": (
                "Not enough human-labeled pairs in this window (need at least 6 GOOD+BAD labels "
                "to suggest thresholds). This is unrelated to the match horizon in days."
            ),
            "by_match_type": by_match_type,
        }

    bad_ratio = bad / total if total else 0.0
    suggested_u = base_u + max(0.0, bad_ratio - 0.18) * 0.35
    suggested_u = min(0.93, max(0.52, suggested_u))

    suggested_f = base_f
    if bad_ratio > 0.3:
        suggested_f = min(0.92, base_f + 0.03)
    elif bad_ratio < 0.12 and good >= 8:
        suggested_f = max(0.78, base_f - 0.02)

    fuzzy_bad = sum(
        by_match_type.get(mt, {}).get(HumanMatchFeedback.BAD.value, 0)
        for mt in (MatchType.FUZZY_REF.value, MatchType.FAMILY_MATCH.value, MatchType.ALIAS_MATCH.value)
    )
    if fuzzy_bad >= 3 and bad_ratio > 0.2:
        suggested_u = min(0.93, suggested_u + 0.02)

    return {
        "unpriced_alert_min_match_confidence": round(suggested_u, 4),
        "exact_reference_match_score_floor": round(suggested_f, 4),
        "rationale": (
            f"n={total}, good={good}, bad={bad}, bad_ratio={bad_ratio:.2f}; "
            "unpriced alert confidence is nudged when BAD share is high."
        ),
        "by_match_type": by_match_type,
    }


async def aggregate_match_feedback_stats(
    session: AsyncSession,
    workspace_id: UUID,
    since_days: int = 30,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, since_days))
    rows = (
        await session.execute(
            select(Match.human_feedback, Match.match_type, Match.expected_profit).where(
                Match.workspace_id == workspace_id,
                Match.human_feedback.isnot(None),
                Match.human_feedback_at.isnot(None),
                Match.human_feedback_at >= cutoff,
            )
        )
    ).all()

    counts: dict[str, int] = defaultdict(int)
    by_match_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    priced: dict[str, int] = defaultdict(int)

    for row in rows:
        feedback, mtype, profit = row[0], row[1], row[2]
        if feedback not in (HumanMatchFeedback.GOOD.value, HumanMatchFeedback.BAD.value):
            continue
        counts[str(feedback)] += 1
        mt = str(mtype) if mtype else "UNKNOWN"
        by_match_type[mt][str(feedback)] += 1
        is_unpriced = profit is None
        key = f"{feedback}_{'unpriced' if is_unpriced else 'priced'}"
        priced[key] += 1

    return {
        "since_days": since_days,
        "since_cutoff_utc": cutoff.isoformat(),
        "counts": dict(counts),
        "by_match_type": {k: dict(v) for k, v in by_match_type.items()},
        "priced_breakdown": dict(priced),
    }


async def apply_workspace_match_calibration(
    session: AsyncSession,
    workspace: Workspace,
    *,
    use_suggestion: bool,
    since_days: int,
    unpriced: float | None,
    exact_floor: float | None,
    reset: bool,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if reset:
        base = dict(workspace.settings_json or {})
        base.pop(MATCH_CALIBRATION_KEY, None)
        workspace.settings_json = base
        await session.flush()
        return {}

    cal = calibration_from_workspace(workspace)

    if use_suggestion:
        agg = await aggregate_match_feedback_stats(session, workspace.id, since_days)
        sug = suggest_calibration(settings, agg["counts"], agg["by_match_type"])
        cal["last_auto_rationale"] = sug.get("rationale")
        if sug.get("unpriced_alert_min_match_confidence") is not None:
            cal["unpriced_alert_min_match_confidence"] = sug["unpriced_alert_min_match_confidence"]
        if sug.get("exact_reference_match_score_floor") is not None:
            cal["exact_reference_match_score_floor"] = sug["exact_reference_match_score_floor"]

    if unpriced is not None:
        cal["unpriced_alert_min_match_confidence"] = float(max(0.35, min(0.99, unpriced)))
    if exact_floor is not None:
        cal["exact_reference_match_score_floor"] = float(max(0.5, min(0.99, exact_floor)))
    if max_age_days is not None:
        cal["match_candidate_max_age_days"] = int(max(1, min(365, int(max_age_days))))

    cal["updated_at"] = datetime.now(timezone.utc).isoformat()

    new_settings = dict(workspace.settings_json or {})
    new_settings[MATCH_CALIBRATION_KEY] = cal
    workspace.settings_json = new_settings
    await session.flush()
    return cal
