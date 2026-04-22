"""Test fixtures: in-memory SQLite via aiosqlite for fast pipeline tests.

The cross-dialect `JSONB` and `GUID` types in `app.models._types` already
fall back to JSON / CHAR(36) on SQLite. We only need to monkeypatch the
pgvector `Vector` type because it has no SQLite equivalent.
"""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_ENABLED", "false")
os.environ.setdefault("TELEGRAM_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("WEBHOOK_HMAC_SECRET", "test-secret")

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.types import JSON  # noqa: E402


def _patch_vector_for_sqlite() -> None:
    """Replace pgvector Vector with a JSON-backed shim before models import."""
    from pgvector import sqlalchemy as pgv

    class _ShimVector(JSON):
        cache_ok = True

        def __init__(self, dim: int | None = None) -> None:
            super().__init__()
            self.dim = dim

    pgv.Vector = _ShimVector  # type: ignore[attr-defined]


_patch_vector_for_sqlite()

from app.core.database import Base  # noqa: E402
from app.models import Workspace  # noqa: E402,F401
import app.models  # noqa: E402,F401


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def workspace(session: AsyncSession) -> Workspace:
    ws = Workspace(name="test-ws", settings_json={})
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws
