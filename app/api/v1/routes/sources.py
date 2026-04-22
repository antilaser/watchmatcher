from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import SourceType
from app.models import SourceAccount

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    source_type: SourceType
    account_name: str


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    source_type: SourceType
    account_name: str
    status: str
    metadata_json: dict
    created_at: datetime


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(body: SourceCreate, workspace: WorkspaceDep, session: SessionDep):
    src = SourceAccount(
        workspace_id=workspace.id,
        source_type=body.source_type,
        account_name=body.account_name,
        status="ACTIVE",
        metadata_json={},
    )
    session.add(src)
    await session.commit()
    await session.refresh(src)
    return SourceOut.model_validate(src)


@router.get("", response_model=list[SourceOut])
async def list_sources(workspace: WorkspaceDep, session: SessionDep):
    rows = (
        await session.execute(
            select(SourceAccount).where(SourceAccount.workspace_id == workspace.id)
        )
    ).scalars().all()
    return [SourceOut.model_validate(r) for r in rows]


@router.get("/{source_id}", response_model=SourceOut)
async def get_source(source_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    row = (
        await session.execute(
            select(SourceAccount).where(
                SourceAccount.id == source_id,
                SourceAccount.workspace_id == workspace.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "source not found")
    return SourceOut.model_validate(row)
