from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import MatchStatus, ReviewActionType, ReviewTargetType
from app.models import Match
from app.review.service import ReviewError, ReviewService
from app.schemas.common import Page
from app.schemas.match import MatchOut

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=Page[MatchOut])
async def list_matches(
    workspace: WorkspaceDep,
    session: SessionDep,
    status_filter: MatchStatus | None = Query(default=None, alias="status"),
    profitable_only: bool = Query(default=False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    base = select(Match).where(Match.workspace_id == workspace.id)
    if status_filter:
        base = base.where(Match.status == status_filter)
    if profitable_only:
        base = base.where(Match.expected_profit.is_not(None)).where(Match.expected_profit > 0)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(base.order_by(Match.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return Page[MatchOut](
        items=[MatchOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{match_id}", response_model=MatchOut)
async def get_match(match_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(Match).where(
                Match.id == match_id,
                Match.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "match not found")
    return MatchOut.model_validate(row)


@router.post("/{match_id}/approve")
async def approve_match(match_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.MATCH,
            target_id=match_id,
            action_type=ReviewActionType.APPROVE_MATCH,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}


@router.post("/{match_id}/reject")
async def reject_match(match_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.MATCH,
            target_id=match_id,
            action_type=ReviewActionType.REJECT_MATCH,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}
