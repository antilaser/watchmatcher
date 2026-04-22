"""Webhook provider — push-based.

The actual HTTP endpoint lives in `app/api/v1/routes/ingest.py`.
This module exists only to mark the provider type and provide constants.
"""

from __future__ import annotations


class WebhookProvider:
    name = "webhook"

    async def poll_messages(self):
        return []
