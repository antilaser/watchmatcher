from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.review.service import ReviewError, ReviewService
from app.schemas.review import ReviewActionRequest

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/action")
async def perform_review_action(
    body: ReviewActionRequest,
    workspace: WorkspaceDep,
    session: SessionDep,
):
    svc = ReviewService(session)
    try:
        await svc.perform(
            workspace_id=workspace.id,
            target_type=body.target_type,
            target_id=body.target_id,
            action_type=body.action_type,
            note=body.note,
        )
    except ReviewError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await session.commit()
    return {"ok": True}
