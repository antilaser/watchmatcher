"""Deterministic dedupe hash for raw messages."""

from __future__ import annotations

import hashlib
from datetime import datetime


def compute_dedupe_hash(
    source_account: str,
    external_group_id: str,
    external_message_id: str | None,
    text_body: str,
    original_timestamp: datetime,
) -> str:
    """Stable hash for idempotent ingestion.

    If `external_message_id` is provided we use it as the strong key.
    Otherwise fall back to a content+timestamp hash.
    """
    if external_message_id:
        key = f"{source_account}|{external_group_id}|{external_message_id}"
    else:
        ts_iso = original_timestamp.isoformat()
        key = f"{source_account}|{external_group_id}|{ts_iso}|{text_body.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
