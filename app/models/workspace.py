from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPKMixin


class Workspace(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
