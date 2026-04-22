from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import BuyRequestStatus, ReviewActionType, ReviewTargetType
from app.models import BuyRequest
from app.review.service import ReviewError, ReviewService
from app.schemas.common import Page
from app.schemas.request import BuyRequestOut

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=Page[BuyRequestOut])
async def list_requests(
    workspace: WorkspaceDep,
    session: SessionDep,
    status_filter: BuyRequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    base = select(BuyRequest).where(BuyRequest.workspace_id == workspace.id)
    if status_filter:
        base = base.where(BuyRequest.status == status_filter)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(base.order_by(BuyRequest.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return Page[BuyRequestOut](
        items=[BuyRequestOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=BuyRequestOut)
async def get_request(request_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(BuyRequest).where(
                BuyRequest.id == request_id,
                BuyRequest.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
    return BuyRequestOut.model_validate(row)


@router.post("/{request_id}/close")
async def close_request(request_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.BUY_REQUEST,
            target_id=request_id,
            action_type=ReviewActionType.CLOSE_BUY_REQUEST,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}


@router.post("/{request_id}/archive")
async def archive_request(request_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.BUY_REQUEST,
            target_id=request_id,
            action_type=ReviewActionType.ARCHIVE,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}
