from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import GUID

from app.core.database import Base
from app.core.enums import GroupType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class Group(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("source_account_id", "external_group_id", name="uq_groups_account_extid"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("source_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_group_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_type: Mapped[GroupType] = mapped_column(
        String(32), nullable=False, default=GroupType.UNKNOWN
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
