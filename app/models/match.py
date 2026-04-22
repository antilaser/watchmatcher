from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from app.models._types import GUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import MatchStatus, MatchType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class Match(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("sell_offer_id", "buy_request_id", name="uq_matches_offer_request"),
        Index("ix_matches_status", "status"),
        Index("ix_matches_expected_profit", "expected_profit"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sell_offer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("sell_offers.id", ondelete="CASCADE"),
        nullable=False,
    )
    buy_request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("buy_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    watch_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("watch_entities.id", ondelete="SET NULL"),
        nullable=True,
    )

    match_type: Mapped[MatchType] = mapped_column(String(32), nullable=False)
    match_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)

    seller_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    buyer_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    seller_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    buyer_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fee_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    risk_buffer: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_profit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    status: Mapped[MatchStatus] = mapped_column(
        String(32), nullable=False, default=MatchStatus.PENDING_REVIEW
    )
    reasoning_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
