"""In-memory / file-backed fake provider used by tests and seed scripts."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.message import IncomingMessage


class FakeProvider:
    name = "fake"

    def __init__(self, messages: list[IncomingMessage] | None = None) -> None:
        self._queue: list[IncomingMessage] = list(messages or [])

    @classmethod
    def from_json_file(cls, path: str | Path) -> FakeProvider:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([IncomingMessage(**m) for m in data])

    def push(self, message: IncomingMessage) -> None:
        self._queue.append(message)

    async def poll_messages(self) -> list[IncomingMessage]:
        out, self._queue = self._queue, []
        return out
