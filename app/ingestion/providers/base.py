"""Provider abstraction for any message source (WhatsApp, Telegram, fakes)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.message import IncomingMessage


@runtime_checkable
class MessageSourceProvider(Protocol):
    """Pull-based provider interface.

    Implementations must be idempotent and safe to call repeatedly.
    Push-based providers (webhooks) bypass `poll_messages` and call
    the ingestion service directly.
    """

    name: str

    async def poll_messages(self) -> list[IncomingMessage]:
        ...
