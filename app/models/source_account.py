from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import GUID

from app.core.database import Base
from app.core.enums import SourceType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class SourceAccount(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "source_accounts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ACTIVE")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
