from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AlarmTarget = Literal["SELL", "BUY", "ANY"]


class SearchAlarmBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_type: AlarmTarget = "SELL"
    is_active: bool = True
    brand: str | None = Field(default=None, max_length=128)
    reference: str | None = Field(default=None, max_length=64)
    year_min: int | None = Field(default=None, ge=1900, le=2099)
    year_max: int | None = Field(default=None, ge=1900, le=2099)
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)


class SearchAlarmCreate(SearchAlarmBase):
    pass


class SearchAlarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_type: AlarmTarget | None = None
    is_active: bool | None = None
    brand: str | None = Field(default=None, max_length=128)
    reference: str | None = Field(default=None, max_length=64)
    year_min: int | None = Field(default=None, ge=1900, le=2099)
    year_max: int | None = Field(default=None, ge=1900, le=2099)
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)


class SearchAlarmOut(SearchAlarmBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime
