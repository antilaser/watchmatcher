"""Common FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Workspace


SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_default_workspace(session: SessionDep) -> Workspace:
    name = get_settings().default_workspace_name
    stmt = select(Workspace).where(Workspace.name == name)
    ws = (await session.execute(stmt)).scalar_one_or_none()
    if ws is None:
        ws = Workspace(name=name, settings_json={})
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
    return ws


WorkspaceDep = Annotated[Workspace, Depends(get_default_workspace)]
