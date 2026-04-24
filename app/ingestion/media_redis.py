"""Temporary storage for WhatsApp image payloads before worker vision step."""

from __future__ import annotations

import base64
import json
from uuid import UUID

import redis.asyncio as redis

from app.core.config import get_settings

KEY_PREFIX = "watchmatch:waimg:"
TTL_SECONDS = 86_400


def _key(raw_message_id: UUID) -> str:
    return f"{KEY_PREFIX}{raw_message_id}"


async def store_pending_image(
    raw_message_id: UUID,
    *,
    image_base64: str,
    image_mime_type: str,
) -> None:
    settings = get_settings()
    payload = json.dumps({"mime": image_mime_type, "b64": image_base64})
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.setex(_key(raw_message_id), TTL_SECONDS, payload)
    finally:
        await client.aclose()


async def pop_pending_image(raw_message_id: UUID) -> tuple[bytes, str] | None:
    """Return (bytes, mime) and delete key, or None if missing."""
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = await client.get(_key(raw_message_id))
        await client.delete(_key(raw_message_id))
        if not raw:
            return None
        data = json.loads(raw)
        b64 = data.get("b64") or ""
        mime = data.get("mime") or "image/jpeg"
        if not b64:
            return None
        return base64.b64decode(b64), mime
    finally:
        await client.aclose()
