from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPKMixin
from app.models._types import GUID, JSONB


class SearchAlarm(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "search_alarms"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SELL", index=True
    )  # SELL, BUY, ANY
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    dial_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bezel_color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    case_material: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bracelet_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
