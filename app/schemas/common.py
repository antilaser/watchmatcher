from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class IDOut(ORMBase):
    id: UUID


class TimestampedOut(ORMBase):
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    env: str
