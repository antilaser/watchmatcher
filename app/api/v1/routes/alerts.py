from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import aliased
from fastapi.responses import FileResponse
from starlette.responses import Response

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import AlertStatus, AlertType, HumanMatchFeedback, MatchStatus
from app.ingestion.image_store import resolve_media_path
from app.models import Alert, BuyRequest, Group, Match, RawMessage, SellOffer
from app.schemas.alert import AlertGroupRef, AlertListItemOut, AlertOut, SnoozeRequest
from app.schemas.common import Page

router = APIRouter(prefix="/alerts", tags=["alerts"])

INACTIVE_MATCH_STATUSES = (MatchStatus.EXPIRED, MatchStatus.REJECTED)


def _has_listing_image(metadata: dict | None) -> bool:
    rel_path = (metadata or {}).get("listing_image_path")
    return isinstance(rel_path, str) and bool(rel_path.strip())


def _image_url(alert_id: UUID, side: str, metadata: dict | None) -> str | None:
    if not _has_listing_image(metadata):
        return None
    return f"/api/v1/alerts/{alert_id}/{side}-image"


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
    review_filter: str | None = Query(
        default=None,
        description="Operator-facing filter: active, reviewed, or errors",
    ),
    alert_type: AlertType | None = Query(default=None),
    hide_human_bad: bool = Query(
        default=False,
        description="Exclude alerts whose match was labeled BAD by an operator",
    ),
    hide_inactive_matches: bool = Query(
        default=False,
        description="Exclude alerts linked to expired/rejected matches",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    filters = [Alert.workspace_id == workspace.id]
    if status_filter:
        filters.append(Alert.status == status_filter)
    if review_filter == "active":
        filters.append(Alert.status.in_((AlertStatus.PENDING, AlertStatus.SENT)))
    elif review_filter == "reviewed":
        filters.append(Alert.status == AlertStatus.ACKNOWLEDGED)
    elif review_filter == "errors":
        filters.append(Alert.status == AlertStatus.FAILED)
    if alert_type:
        filters.append(Alert.alert_type == alert_type)

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
    if hide_inactive_matches:
        count_base = count_base.where(
            or_(
                Alert.match_id.is_(None),
                Match.status.is_(None),
                Match.status.notin_(INACTIVE_MATCH_STATUSES),
            )
        )
    total = (await session.execute(count_base)).scalar_one()

    sell_rm = aliased(RawMessage)
    buy_rm = aliased(RawMessage)
    sell_g = aliased(Group)
    buy_g = aliased(Group)

    list_stmt = (
        select(
            Alert,
            sell_g,
            buy_g,
            Match.human_feedback,
            Match.human_feedback_note,
            sell_rm.text_body,
            buy_rm.text_body,
            sell_rm.original_timestamp,
            buy_rm.original_timestamp,
            sell_rm.metadata_json,
            buy_rm.metadata_json,
            Match.status,
        )
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
    if hide_inactive_matches:
        list_stmt = list_stmt.where(
            or_(
                Alert.match_id.is_(None),
                Match.status.is_(None),
                Match.status.notin_(INACTIVE_MATCH_STATUSES),
            )
        )
    active_sort = case(
        (Match.status.in_(INACTIVE_MATCH_STATUSES), 1),
        else_=0,
    )
    rows = (
        await session.execute(
            list_stmt.order_by(active_sort, Alert.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    items: list[AlertListItemOut] = []
    for (
        alert,
        sell_gr,
        buy_gr,
        human_fb,
        human_fb_note,
        seller_text,
        buyer_text,
        seller_message_at,
        buyer_message_at,
        seller_metadata,
        buyer_metadata,
        match_status,
    ) in rows:
        base = AlertOut.model_validate(alert).model_dump()
        payload = alert.payload_json or {}
        items.append(
            AlertListItemOut(
                **base,
                sell_group=_group_ref(sell_gr),
                buy_group=_group_ref(buy_gr),
                seller_message_text=payload.get("seller_message_text") or seller_text,
                buyer_message_text=payload.get("buyer_message_text") or buyer_text,
                seller_message_at=seller_message_at or payload.get("seller_message_at"),
                buyer_message_at=buyer_message_at or payload.get("buyer_message_at"),
                seller_image_url=_image_url(alert.id, "seller", seller_metadata),
                buyer_image_url=_image_url(alert.id, "buyer", buyer_metadata),
                match_status=match_status,
                match_human_feedback=human_fb,
                match_human_feedback_note=human_fb_note,
            )
        )

    return Page[AlertListItemOut](
        items=items,
        total=int(total),
        limit=limit,
        offset=offset,
    )


async def _alert_side_image(
    alert_id: UUID,
    side: str,
    workspace: WorkspaceDep,
    session: SessionDep,
) -> FileResponse:
    sell_rm = aliased(RawMessage)
    buy_rm = aliased(RawMessage)
    row = (
        await session.execute(
            select(sell_rm.metadata_json, buy_rm.metadata_json)
            .select_from(Alert)
            .outerjoin(Match, Alert.match_id == Match.id)
            .outerjoin(SellOffer, Match.sell_offer_id == SellOffer.id)
            .outerjoin(sell_rm, SellOffer.raw_message_id == sell_rm.id)
            .outerjoin(BuyRequest, Match.buy_request_id == BuyRequest.id)
            .outerjoin(buy_rm, BuyRequest.raw_message_id == buy_rm.id)
            .where(Alert.id == alert_id, Alert.workspace_id == workspace.id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert image not found")

    metadata = row[0] if side == "seller" else row[1]
    rel_path = (metadata or {}).get("listing_image_path")
    if not isinstance(rel_path, str) or not rel_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert image not found")
    try:
        path = resolve_media_path(rel_path)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert image not found") from e
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert image not found")
    return FileResponse(path, media_type=(metadata or {}).get("listing_image_mime_type") or "image/jpeg")


@router.get("/{alert_id}/seller-image")
async def get_alert_seller_image(
    alert_id: UUID,
    workspace: WorkspaceDep,
    session: SessionDep,
) -> FileResponse:
    return await _alert_side_image(alert_id, "seller", workspace, session)


@router.get("/{alert_id}/buyer-image")
async def get_alert_buyer_image(
    alert_id: UUID,
    workspace: WorkspaceDep,
    session: SessionDep,
) -> FileResponse:
    return await _alert_side_image(alert_id, "buyer", workspace, session)


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
