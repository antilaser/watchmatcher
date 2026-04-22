from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ReviewActionType, ReviewTargetType


class ReviewActionRequest(BaseModel):
    target_type: ReviewTargetType
    target_id: UUID
    action_type: ReviewActionType
    note: str | None = None
