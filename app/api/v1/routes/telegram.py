from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.alerts.telegram import TelegramClient, build_match_horizon_keyboard
from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.config import get_settings
from app.matching.calibration import (
    apply_workspace_match_calibration,
    effective_match_candidate_max_age_days,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _expected_secret() -> str:
    settings = get_settings()
    return settings.telegram_webhook_secret or settings.webhook_hmac_secret


def _chat_id(update: dict[str, Any]) -> str | None:
    msg = update.get("message") or update.get("edited_message")
    if isinstance(msg, dict):
        chat = msg.get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            return str(chat["id"])
    cb = update.get("callback_query")
    if isinstance(cb, dict):
        msg = cb.get("message")
        if isinstance(msg, dict):
            chat = msg.get("chat")
            if isinstance(chat, dict) and chat.get("id") is not None:
                return str(chat["id"])
    return None


def _parse_days(text: str) -> int | None:
    parts = text.strip().split()
    if len(parts) != 2 or parts[0].lower() not in {"/horizon", "/matchdays"}:
        return None
    try:
        days = int(parts[1])
    except ValueError:
        return None
    if days < 1 or days > 365:
        return None
    return days


async def _set_horizon(session: SessionDep, workspace: WorkspaceDep, days: int) -> dict[str, object]:
    cal = await apply_workspace_match_calibration(
        session,
        workspace,
        use_suggestion=False,
        since_days=30,
        unpriced=None,
        exact_floor=None,
        reset=False,
        max_age_days=days,
    )
    await session.commit()
    await session.refresh(workspace)
    return cal


async def _send_horizon_status(chat_id: str, workspace: WorkspaceDep) -> None:
    settings = get_settings()
    current = effective_match_candidate_max_age_days(settings, workspace)
    client = TelegramClient()
    await client.send_message(
        chat_id=chat_id,
        text=(
            "Match search horizon\n"
            f"Current value: {current} days\n\n"
            "This controls how far back the system looks for the opposite side of a match "
            "(seller vs buyer) by original WhatsApp message time.\n\n"
            "Set it with /horizon 14 or use a quick button below."
        ),
        reply_markup=build_match_horizon_keyboard(),
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    workspace: WorkspaceDep,
    session: SessionDep,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = get_settings()
    expected = _expected_secret()
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram webhook secret not configured")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
        x_telegram_bot_api_secret_token,
        expected,
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid telegram webhook secret")

    update = await request.json()
    chat_id = _chat_id(update)
    if not chat_id:
        return {"ok": True}
    if settings.telegram_default_chat_id and chat_id != settings.telegram_default_chat_id:
        return {"ok": True}

    client = TelegramClient()
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        data = str(callback.get("data") or "")
        callback_id = str(callback.get("id") or "")
        if data.startswith("horizon:"):
            try:
                days = int(data.split(":", 1)[1])
            except ValueError:
                days = 0
            if 1 <= days <= 365:
                await _set_horizon(session, workspace, days)
                if callback_id:
                    await client.answer_callback_query(callback_id, f"Match horizon set to {days} days")
                await client.send_message(chat_id=chat_id, text=f"Match horizon set to {days} days.")
        return {"ok": True}

    msg = update.get("message") or {}
    text = str(msg.get("text") or "").strip()
    if text.lower() in {"/horizon", "/matchdays"}:
        await _send_horizon_status(chat_id, workspace)
    elif text.lower().startswith(("/horizon ", "/matchdays ")):
        days = _parse_days(text)
        if days is None:
            await client.send_message(chat_id=chat_id, text="Use /horizon N where N is 1-365 days.")
        else:
            await _set_horizon(session, workspace, days)
            await client.send_message(chat_id=chat_id, text=f"Match horizon set to {days} days.")
    return {"ok": True}
