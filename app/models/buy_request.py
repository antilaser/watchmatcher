from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from app.models._types import GUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import BuyRequestStatus
from app.models._mixins import TimestampMixin, UUIDPKMixin


class BuyRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "buy_requests"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("raw_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parsed_message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("parsed_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    watch_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("watch_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    brand_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)

    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    location_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[BuyRequestStatus] = mapped_column(
        String(32), nullable=False, default=BuyRequestStatus.OPEN, index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
