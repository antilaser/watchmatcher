from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased
from starlette.responses import Response

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import AlertStatus, HumanMatchFeedback
from app.models import Alert, BuyRequest, Group, Match, RawMessage, SellOffer
from app.schemas.alert import AlertGroupRef, AlertListItemOut, AlertOut, SnoozeRequest
from app.schemas.common import Page

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _group_ref(row: Group | None) -> AlertGroupRef | None:
    if row is None:
        return None
    invite_url = (
        f"https://chat.whatsapp.com/{row.invite_code}" if row.invite_code else None
    )
    return AlertGroupRef(
        id=row.id,
        group_name=row.group_name,
        external_group_id=row.external_group_id,
        invite_url=invite_url,
    )


@router.get("", response_model=Page[AlertListItemOut])
async def list_alerts(
    workspace: WorkspaceDep,
    session: SessionDep,
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    hide_human_bad: bool = Query(
        default=False,
        description="Exclude alerts whose match was labeled BAD by an operator",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    filters = [Alert.workspace_id == workspace.id]
    if status_filter:
        filters.append(Alert.status == status_filter)

    count_base = select(func.count(Alert.id)).select_from(Alert).outerjoin(
        Match, Alert.match_id == Match.id
    )
    count_base = count_base.where(*filters)
    if hide_human_bad:
        count_base = count_base.where(
            or_(
                Match.human_feedback.is_(None),
                Match.human_feedback != HumanMatchFeedback.BAD.value,
            )
        )
    total = (await session.execute(count_base)).scalar_one()

    sell_rm = aliased(RawMessage)
    buy_rm = aliased(RawMessage)
    sell_g = aliased(Group)
    buy_g = aliased(Group)

    list_stmt = (
        select(Alert, sell_g, buy_g, Match.human_feedback)
        .outerjoin(Match, Alert.match_id == Match.id)
        .outerjoin(SellOffer, Match.sell_offer_id == SellOffer.id)
        .outerjoin(sell_rm, SellOffer.raw_message_id == sell_rm.id)
        .outerjoin(sell_g, sell_rm.group_id == sell_g.id)
        .outerjoin(BuyRequest, Match.buy_request_id == BuyRequest.id)
        .outerjoin(buy_rm, BuyRequest.raw_message_id == buy_rm.id)
        .outerjoin(buy_g, buy_rm.group_id == buy_g.id)
        .where(*filters)
    )
    if hide_human_bad:
        list_stmt = list_stmt.where(
            or_(
                Match.human_feedback.is_(None),
                Match.human_feedback != HumanMatchFeedback.BAD.value,
            )
        )
    rows = (
        await session.execute(
            list_stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    items: list[AlertListItemOut] = []
    for alert, sell_gr, buy_gr, human_fb in rows:
        base = AlertOut.model_validate(alert).model_dump()
        items.append(
            AlertListItemOut(
                **base,
                sell_group=_group_ref(sell_gr),
                buy_group=_group_ref(buy_gr),
                match_human_feedback=human_fb,
            )
        )

    return Page[AlertListItemOut](
        items=items,
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


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: UUID, workspace: WorkspaceDep, session: SessionDep):
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.workspace_id == workspace.id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    await session.delete(alert)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
