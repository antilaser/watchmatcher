from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import GroupType
from app.models import Group

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    source_account_id: UUID
    external_group_id: str
    group_name: str
    group_type: GroupType
    is_active: bool
    created_at: datetime


class GroupPatch(BaseModel):
    group_name: str | None = None
    group_type: GroupType | None = None
    is_active: bool | None = None


@router.get("", response_model=list[GroupOut])
async def list_groups(workspace: WorkspaceDep, session: SessionDep):
    rows = (
        await session.execute(select(Group).where(Group.workspace_id == workspace.id))
    ).scalars().all()
    return [GroupOut.model_validate(r) for r in rows]


@router.patch("/{group_id}", response_model=GroupOut)
async def patch_group(
    group_id: UUID,
    body: GroupPatch,
    workspace: WorkspaceDep,
    session: SessionDep,
):
    row = (
        await session.execute(
            select(Group).where(Group.id == group_id, Group.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return GroupOut.model_validate(row)
