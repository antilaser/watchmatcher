from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, text
from starlette.responses import Response

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.models import Alert, Group, RawMessage, SearchAlarm
from app.schemas.common import Page
from app.schemas.search_alarm import (
    SearchAlarmCreate,
    SearchAlarmOut,
    SearchAlarmTriggerOut,
    SearchAlarmUpdate,
)

router = APIRouter(prefix="/search-alarms", tags=["search-alarms"])


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


def _clean_lower(v: str | None) -> str | None:
    s = _clean(v)
    return s.lower() if s else None


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
        dial_color=_clean_lower(body.dial_color),
        bezel_color=_clean_lower(body.bezel_color),
        case_material=_clean_lower(body.case_material),
        bracelet_type=_clean_lower(body.bracelet_type),
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
        if key in {"dial_color", "bezel_color", "case_material", "bracelet_type"}:
            value = _clean_lower(value)
        if key == "name" and value is not None:
            value = value.strip()
        setattr(alarm, key, value)
    await session.commit()
    await session.refresh(alarm)
    return alarm


@router.get("/{alarm_id}/alerts", response_model=Page[SearchAlarmTriggerOut])
async def list_search_alarm_alerts(
    alarm_id: UUID,
    workspace: WorkspaceDep,
    session: SessionDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    alarm = (
        await session.execute(
            select(SearchAlarm).where(SearchAlarm.id == alarm_id, SearchAlarm.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "search alarm not found")

    alarm_filter = text("alerts.payload_json ->> 'search_alarm_id' = :alarm_id").bindparams(
        alarm_id=str(alarm_id)
    )
    total = int(
        (
            await session.execute(
                select(func.count(Alert.id))
                .where(Alert.workspace_id == workspace.id)
                .where(alarm_filter)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(Alert, RawMessage, Group)
            .outerjoin(RawMessage, RawMessage.id == Alert.raw_message_id)
            .outerjoin(Group, Group.id == RawMessage.group_id)
            .where(Alert.workspace_id == workspace.id)
            .where(alarm_filter)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = []
    for alert, raw, group in rows:
        payload = alert.payload_json or {}
        invite_url = f"https://chat.whatsapp.com/{group.invite_code}" if group and group.invite_code else None
        items.append(
            SearchAlarmTriggerOut(
                id=alert.id,
                raw_message_id=alert.raw_message_id,
                sender_name=raw.sender_name if raw else None,
                sender_external_id=raw.sender_external_id if raw else None,
                group_name=group.group_name if group else None,
                group_invite_url=invite_url,
                external_message_id=raw.external_message_id if raw else None,
                message_at=raw.original_timestamp if raw else None,
                status=alert.status.value if hasattr(alert.status, "value") else str(alert.status),
                channel=alert.channel.value if hasattr(alert.channel, "value") else str(alert.channel),
                summary=payload.get("summary"),
                seller_message_text=payload.get("seller_message_text"),
                buyer_message_text=payload.get("buyer_message_text"),
                created_at=alert.created_at,
            )
        )
    return Page[SearchAlarmTriggerOut](items=items, total=total, limit=limit, offset=offset)


@router.delete("/{alarm_id}/alerts", status_code=status.HTTP_200_OK)
async def delete_search_alarm_alerts(alarm_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    alarm = (
        await session.execute(
            select(SearchAlarm).where(SearchAlarm.id == alarm_id, SearchAlarm.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "search alarm not found")

    alarm_filter = text("alerts.payload_json ->> 'search_alarm_id' = :alarm_id").bindparams(
        alarm_id=str(alarm_id)
    )
    rows = (
        await session.execute(
            select(Alert)
            .where(Alert.workspace_id == workspace.id)
            .where(alarm_filter)
        )
    ).scalars().all()
    deleted = len(rows)
    for alert in rows:
        await session.delete(alert)
    await session.commit()
    return {"ok": True, "deleted": deleted}


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
