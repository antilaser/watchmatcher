from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import MatchStatus, MatchType


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    sell_offer_id: UUID
    buy_request_id: UUID
    watch_entity_id: UUID | None
    match_type: MatchType
    match_confidence: float
    seller_price: Decimal | None
    buyer_price: Decimal | None
    seller_currency: str | None
    buyer_currency: str | None
    fx_rate: Decimal | None
    shipping_cost: Decimal | None
    fee_cost: Decimal | None
    risk_buffer: Decimal | None
    expected_profit: Decimal | None
    status: MatchStatus
    reasoning_json: dict
    created_at: datetime
