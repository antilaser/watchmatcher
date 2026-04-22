from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import BuyRequestStatus


class BuyRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    raw_message_id: UUID
    parsed_message_id: UUID
    watch_entity_id: UUID | None
    brand_raw: str | None
    family_raw: str | None
    reference_raw: str | None
    target_price: Decimal | None
    currency: str | None
    buyer_name: str | None
    status: BuyRequestStatus
    confidence: float
    created_at: datetime
    closed_at: datetime | None
