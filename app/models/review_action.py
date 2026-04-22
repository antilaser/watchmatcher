from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import GUID

from app.core.database import Base
from app.core.enums import ReviewActionType, ReviewTargetType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class ReviewAction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "review_actions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    target_type: Mapped[ReviewTargetType] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    action_type: Mapped[ReviewActionType] = mapped_column(String(48), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
