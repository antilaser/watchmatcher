from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from starlette.responses import Response

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.models import SearchAlarm
from app.schemas.common import Page
from app.schemas.search_alarm import SearchAlarmCreate, SearchAlarmOut, SearchAlarmUpdate

router = APIRouter(prefix="/search-alarms", tags=["search-alarms"])


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


@router.get("", response_model=Page[SearchAlarmOut])
async def list_search_alarms(
    workspace: WorkspaceDep,
    session: SessionDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    total = int(
        (
            await session.execute(
                select(func.count(SearchAlarm.id)).where(SearchAlarm.workspace_id == workspace.id)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(SearchAlarm)
            .where(SearchAlarm.workspace_id == workspace.id)
            .order_by(SearchAlarm.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Page[SearchAlarmOut](items=list(rows), total=total, limit=limit, offset=offset)


@router.post("", response_model=SearchAlarmOut, status_code=status.HTTP_201_CREATED)
async def create_search_alarm(
    body: SearchAlarmCreate,
    workspace: WorkspaceDep,
    session: SessionDep,
):
    alarm = SearchAlarm(
        workspace_id=workspace.id,
        name=body.name.strip(),
        target_type=body.target_type,
        is_active=body.is_active,
        brand=_clean(body.brand),
        reference=_clean(body.reference.upper() if body.reference else None),
        year_min=body.year_min,
        year_max=body.year_max,
        price_min=body.price_min,
        price_max=body.price_max,
        currency=_clean(body.currency.upper() if body.currency else None),
        extra_json={},
    )
    session.add(alarm)
    await session.commit()
    await session.refresh(alarm)
    return alarm


@router.patch("/{alarm_id}", response_model=SearchAlarmOut)
async def update_search_alarm(
    alarm_id: UUID,
    body: SearchAlarmUpdate,
    workspace: WorkspaceDep,
    session: SessionDep,
):
    alarm = (
        await session.execute(
            select(SearchAlarm).where(SearchAlarm.id == alarm_id, SearchAlarm.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "search alarm not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in {"brand", "reference", "currency"}:
            value = _clean(str(value).upper() if value is not None and key != "brand" else value)
        if key == "name" and value is not None:
            value = value.strip()
        setattr(alarm, key, value)
    await session.commit()
    await session.refresh(alarm)
    return alarm


@router.delete("/{alarm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_alarm(alarm_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    alarm = (
        await session.execute(
            select(SearchAlarm).where(SearchAlarm.id == alarm_id, SearchAlarm.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "search alarm not found")
    await session.delete(alarm)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
