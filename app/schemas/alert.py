from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import AlertChannel, AlertStatus, AlertType


class AlertGroupRef(BaseModel):
    """Group where a matched offer/request originated (WhatsApp)."""

    id: UUID
    group_name: str
    external_group_id: str
    invite_url: str | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    match_id: UUID | None
    raw_message_id: UUID | None
    alert_type: AlertType
    channel: AlertChannel
    payload_json: dict
    status: AlertStatus
    sent_at: datetime | None
    snoozed_until: datetime | None
    created_at: datetime


class AlertListItemOut(AlertOut):
    """Alert row plus linked groups for dashboard / UI."""

    sell_group: AlertGroupRef | None = None
    buy_group: AlertGroupRef | None = None
    match_human_feedback: str | None = None


class SnoozeRequest(BaseModel):
    minutes: int = 60
