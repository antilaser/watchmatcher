"""Optional pgvector-backed embeddings table."""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import GUID

from app.core.database import Base
from app.core.enums import EmbeddingObjectType
from app.models._mixins import TimestampMixin, UUIDPKMixin

EMBEDDING_DIM = 1536


class Embedding(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index("ix_embeddings_object", "object_type", "object_id"),
    )

    object_type: Mapped[EmbeddingObjectType] = mapped_column(String(32), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
