from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import ReviewActionType, ReviewTargetType, SellOfferStatus
from app.models import SellOffer
from app.review.service import ReviewError, ReviewService
from app.schemas.common import Page
from app.schemas.offer import SellOfferOut

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=Page[SellOfferOut])
async def list_offers(
    workspace: WorkspaceDep,
    session: SessionDep,
    status_filter: SellOfferStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    base = select(SellOffer).where(SellOffer.workspace_id == workspace.id)
    if status_filter:
        base = base.where(SellOffer.status == status_filter)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(base.order_by(SellOffer.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return Page[SellOfferOut](
        items=[SellOfferOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{offer_id}", response_model=SellOfferOut)
async def get_offer(offer_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(SellOffer).where(
                SellOffer.id == offer_id,
                SellOffer.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "offer not found")
    return SellOfferOut.model_validate(row)


@router.post("/{offer_id}/close")
async def close_offer(offer_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.SELL_OFFER,
            target_id=offer_id,
            action_type=ReviewActionType.CLOSE_SELL_OFFER,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}


@router.post("/{offer_id}/archive")
async def archive_offer(offer_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=ReviewTargetType.SELL_OFFER,
            target_id=offer_id,
            action_type=ReviewActionType.ARCHIVE,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}
