from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.dedupe import compute_dedupe_hash


def test_dedupe_external_id_used():
    ts = datetime(2026, 4, 20, tzinfo=timezone.utc)
    a = compute_dedupe_hash("acc", "g", "ext-1", "hello", ts)
    b = compute_dedupe_hash("acc", "g", "ext-1", "different text", ts)
    assert a == b


def test_dedupe_no_external_id_uses_text_and_ts():
    ts = datetime(2026, 4, 20, tzinfo=timezone.utc)
    a = compute_dedupe_hash("acc", "g", None, "hello", ts)
    b = compute_dedupe_hash("acc", "g", None, "hello world", ts)
    assert a != b


def test_dedupe_distinct_groups():
    ts = datetime(2026, 4, 20, tzinfo=timezone.utc)
    a = compute_dedupe_hash("acc", "g1", "ext-1", "hi", ts)
    b = compute_dedupe_hash("acc", "g2", "ext-1", "hi", ts)
    assert a != b
