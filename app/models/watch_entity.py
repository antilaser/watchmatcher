from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from app.models._types import GUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import AliasType
from app.models._mixins import TimestampMixin, UUIDPKMixin


class WatchEntity(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "watch_entities"
    __table_args__ = (
        UniqueConstraint("brand", "family", "reference", name="uq_watch_entities_b_f_r"),
    )

    brand: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aliases_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WatchEntityAlias(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "watch_entity_aliases"
    __table_args__ = (
        UniqueConstraint("watch_entity_id", "alias_text", name="uq_alias_entity_text"),
    )

    watch_entity_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("watch_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alias_type: Mapped[AliasType] = mapped_column(String(32), nullable=False)
    confidence_weight: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.0)
