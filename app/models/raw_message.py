from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import GUID

from app.core.database import Base
from app.core.enums import ProcessingStatus
from app.models._mixins import UUIDPKMixin


class RawMessage(UUIDPKMixin, Base):
    __tablename__ = "raw_messages"
    __table_args__ = (
        UniqueConstraint("group_id", "external_message_id", name="uq_raw_messages_group_extid"),
        Index("ix_raw_messages_dedupe_hash", "dedupe_hash"),
        Index("ix_raw_messages_original_ts", "original_timestamp"),
        Index("ix_raw_messages_processing_status", "processing_status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    original_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        String(32), nullable=False, default=ProcessingStatus.PENDING
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
