"""Minimal Telegram Bot API client (no SDK dependency)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class TelegramClient:
    BASE_URL = "https://api.telegram.org"

    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self._token = token or settings.telegram_bot_token
        self._enabled = bool(self._token) and settings.telegram_enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> bool:
        if not self._enabled:
            log.info("telegram_disabled_send_skipped", chat_id=chat_id)
            return False

        url = f"{self.BASE_URL}/bot{self._token}/sendMessage"
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    log.warning("telegram_send_failed", status=r.status_code, body=r.text)
                    return False
                return True
            except httpx.HTTPError as e:
                log.warning("telegram_http_error", error=str(e))
                return False


def build_match_inline_keyboard(match_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"approve:{match_id}"},
                {"text": "Reject", "callback_data": f"reject:{match_id}"},
            ],
            [
                {"text": "Snooze 1h", "callback_data": f"snooze:{match_id}:60"},
                {"text": "Archive", "callback_data": f"archive:{match_id}"},
            ],
        ]
    }
