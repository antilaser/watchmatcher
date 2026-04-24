from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.models import Workspace
from app.core.config import get_settings
from app.matching.calibration import (
    aggregate_match_feedback_stats,
    apply_workspace_match_calibration,
    calibration_from_workspace,
    suggest_calibration,
)
from app.schemas.calibration import (
    ApplyMatchCalibrationIn,
    MatchCandidateMaxAgeIn,
    MatchFeedbackStatsOut,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/match-feedback-stats", response_model=MatchFeedbackStatsOut)
async def match_feedback_stats(
    workspace: WorkspaceDep,
    session: SessionDep,
    since_days: int = 30,
):
    agg = await aggregate_match_feedback_stats(session, workspace.id, since_days)
    sug = suggest_calibration(get_settings(), agg["counts"], agg["by_match_type"])
    current = calibration_from_workspace(workspace)
    return MatchFeedbackStatsOut(
        since_days=agg["since_days"],
        since_cutoff_utc=agg["since_cutoff_utc"],
        counts=agg["counts"],
        by_match_type=agg["by_match_type"],
        priced_breakdown=agg["priced_breakdown"],
        suggested_calibration=sug,
        current_calibration=current,
    )


async def _apply_match_candidate_max_age(
    workspace: Workspace,
    session: AsyncSession,
    days: int,
) -> dict[str, object]:
    cal = await apply_workspace_match_calibration(
        session,
        workspace,
        use_suggestion=False,
        since_days=30,
        unpriced=None,
        exact_floor=None,
        reset=False,
        max_age_days=days,
    )
    await session.commit()
    await session.refresh(workspace)
    return {"ok": True, "match_calibration": cal}


@router.patch("/match-candidate-max-age", status_code=status.HTTP_200_OK)
async def patch_match_candidate_max_age(
    workspace: WorkspaceDep,
    session: SessionDep,
    body: MatchCandidateMaxAgeIn,
):
    """Save counterpart search horizon only (avoids the full match-calibration gate)."""
    return await _apply_match_candidate_max_age(workspace, session, body.days)


@router.post("/match-candidate-max-age", status_code=status.HTTP_200_OK)
async def post_match_candidate_max_age(
    workspace: WorkspaceDep,
    session: SessionDep,
    body: MatchCandidateMaxAgeIn,
):
    """Same as PATCH — some proxies strip PATCH; POST is more widely forwarded."""
    return await _apply_match_candidate_max_age(workspace, session, body.days)


@router.post("/match-calibration", status_code=status.HTTP_200_OK)
async def apply_match_calibration(
    workspace: WorkspaceDep,
    session: SessionDep,
    body: ApplyMatchCalibrationIn,
):
    # Use parsed fields, not model_dump(exclude_unset=True): unset vs default=None edge cases
    # must not reject horizon-only updates (match_candidate_max_age_days / "days" alias).
    has_action_or_value = (
        body.reset_to_defaults
        or body.use_suggestion
        or body.unpriced_alert_min_match_confidence is not None
        or body.exact_reference_match_score_floor is not None
        or body.match_candidate_max_age_days is not None
    )
    if not has_action_or_value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide reset_to_defaults, use_suggestion, explicit thresholds "
                "(unpriced_alert_min_match_confidence / exact_reference_match_score_floor), "
                "or match_candidate_max_age_days / days — or POST /workspace/match-candidate-max-age with {\"days\": N}."
            ),
        )
    cal = await apply_workspace_match_calibration(
        session,
        workspace,
        use_suggestion=body.use_suggestion,
        since_days=body.since_days,
        unpriced=body.unpriced_alert_min_match_confidence,
        exact_floor=body.exact_reference_match_score_floor,
        reset=body.reset_to_defaults,
        max_age_days=body.match_candidate_max_age_days,
    )
    await session.commit()
    await session.refresh(workspace)
    return {"ok": True, "match_calibration": cal}
