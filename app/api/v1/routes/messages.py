from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.models import RawMessage
from app.schemas.common import Page
from app.schemas.message import RawMessageOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=Page[RawMessageOut])
async def list_messages(
    workspace: WorkspaceDep,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    base = select(RawMessage).where(RawMessage.workspace_id == workspace.id)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base.order_by(RawMessage.original_timestamp.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Page[RawMessageOut](
        items=[RawMessageOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{message_id}", response_model=RawMessageOut)
async def get_message(message_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(RawMessage).where(
                RawMessage.id == message_id,
                RawMessage.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    return RawMessageOut.model_validate(row)


@router.post("/{message_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_message(message_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(RawMessage).where(
                RawMessage.id == message_id,
                RawMessage.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    from app.services.pipeline import PipelineService

    pipeline = PipelineService(session)
    await pipeline.process_raw_message(row.id)
    await session.commit()
    return {"id": str(row.id), "status": row.processing_status}
