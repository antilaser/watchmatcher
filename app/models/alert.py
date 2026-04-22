from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from app.models._types import GUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import AlertChannel, AlertStatus, AlertType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class Alert(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("raw_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[AlertType] = mapped_column(String(48), nullable=False, index=True)
    channel: Mapped[AlertChannel] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[AlertStatus] = mapped_column(
        String(32), nullable=False, default=AlertStatus.PENDING, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
