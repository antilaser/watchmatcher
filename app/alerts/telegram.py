"""Minimal Telegram Bot API client (no SDK dependency)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.image_store import resolve_media_path

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
        parse_mode: str | None = None,
    ) -> bool:
        if not self._enabled:
            log.info("telegram_disabled_send_skipped", chat_id=chat_id)
            return False

        url = f"{self.BASE_URL}/bot{self._token}/sendMessage"
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
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

    async def send_photo(
        self,
        chat_id: str,
        photo_path: str,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> bool:
        if not self._enabled:
            log.info("telegram_disabled_photo_send_skipped", chat_id=chat_id)
            return False

        url = f"{self.BASE_URL}/bot{self._token}/sendPhoto"
        data: dict = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption[:1024]
        if parse_mode is not None:
            data["parse_mode"] = parse_mode

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                with open(photo_path, "rb") as photo:
                    r = await client.post(url, data=data, files={"photo": photo})
                if r.status_code != 200:
                    log.warning("telegram_photo_send_failed", status=r.status_code, body=r.text)
                    return False
                return True
            except (OSError, httpx.HTTPError) as e:
                log.warning("telegram_photo_http_error", error=str(e))
                return False

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> bool:
        if not self._enabled:
            log.info("telegram_disabled_callback_answer_skipped")
            return False

        url = f"{self.BASE_URL}/bot{self._token}/answerCallbackQuery"
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    log.warning("telegram_callback_answer_failed", status=r.status_code, body=r.text)
                    return False
                return True
            except httpx.HTTPError as e:
                log.warning("telegram_callback_answer_http_error", error=str(e))
                return False


def stored_message_photo_path(metadata: dict | None) -> str | None:
    rel_path = (metadata or {}).get("listing_image_path")
    if not isinstance(rel_path, str) or not rel_path:
        return None
    try:
        path = resolve_media_path(rel_path)
    except ValueError:
        return None
    if not path.exists():
        return None
    return str(path)


def build_match_horizon_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "1 day", "callback_data": "horizon:1"},
                {"text": "3 days", "callback_data": "horizon:3"},
                {"text": "7 days", "callback_data": "horizon:7"},
            ],
            [
                {"text": "14 days", "callback_data": "horizon:14"},
                {"text": "30 days", "callback_data": "horizon:30"},
                {"text": "60 days", "callback_data": "horizon:60"},
            ],
        ]
    }
