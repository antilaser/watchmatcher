from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import SellOfferStatus


class SellOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    raw_message_id: UUID
    parsed_message_id: UUID
    watch_entity_id: UUID | None
    brand_raw: str | None
    family_raw: str | None
    reference_raw: str | None
    manufacture_year: int | None = None
    condition_raw: str | None
    dial_color: str | None = None
    dial_variant: str | None = None
    bezel_color: str | None = None
    case_material: str | None = None
    bracelet_type: str | None = None
    visual_confidence: float | None = None
    asking_price: Decimal | None
    currency: str | None
    seller_name: str | None
    status: SellOfferStatus
    confidence: float
    created_at: datetime
    closed_at: datetime | None


class SellListingOut(SellOfferOut):
    """Sell offer joined with source group and WhatsApp message time."""

    group_name: str
    message_at: datetime
    image_url: str | None = None
    text_preview: str | None = None
