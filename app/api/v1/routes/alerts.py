from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import AlertStatus
from app.models import Alert
from app.schemas.alert import AlertOut, SnoozeRequest
from app.schemas.common import Page

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=Page[AlertOut])
async def list_alerts(
    workspace: WorkspaceDep,
    session: SessionDep,
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    base = select(Alert).where(Alert.workspace_id == workspace.id)
    if status_filter:
        base = base.where(Alert.status == status_filter)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(base.order_by(Alert.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return Page[AlertOut](
        items=[AlertOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    alert.status = AlertStatus.ACKNOWLEDGED
    await session.commit()
    return {"ok": True}


@router.post("/{alert_id}/snooze")
async def snooze_alert(
    alert_id: UUID,
    body: SnoozeRequest,
    workspace: WorkspaceDep,
    session: SessionDep,
):
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    alert.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=body.minutes)
    await session.commit()
    return {"ok": True, "snoozed_until": alert.snoozed_until}
