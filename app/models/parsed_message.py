from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from app.models._types import GUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import MessageClassification, ParseMethod
from app.models._mixins import TimestampMixin, UUIDPKMixin


class ParsedMessage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "parsed_messages"

    raw_message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("raw_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    classification: Mapped[MessageClassification] = mapped_column(String(32), nullable=False)
    classification_confidence: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False, default=0.0
    )
    parse_method: Mapped[ParseMethod] = mapped_column(String(16), nullable=False)
    parse_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    extracted_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
