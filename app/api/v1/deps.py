"""Common FastAPI dependencies."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Workspace


SessionDep = Annotated[AsyncSession, Depends(get_db)]
_dashboard_basic = HTTPBasic(auto_error=False)


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


async def require_dashboard_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_dashboard_basic)],
) -> None:
    settings = get_settings()
    if not settings.dashboard_auth_enabled:
        return
    if not settings.dashboard_auth_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard auth is enabled but DASHBOARD_AUTH_PASSWORD is not configured",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.dashboard_auth_username.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.dashboard_auth_password.encode("utf-8"),
    )
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


DashboardAuthDep = Annotated[None, Depends(require_dashboard_auth)]
