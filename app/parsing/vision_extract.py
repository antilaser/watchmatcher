"""OpenAI vision: read watch refs / prices from listing photos (dial, tag, card)."""

from __future__ import annotations

import base64

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_VISION_PROMPT = """You analyze a luxury watch trading chat photo (dial, bracelet, warranty card, dealer tag, sticker).
The reference is often stamped or printed on the warranty card / certificate papers shown next to the watch in the same frame — read those digits carefully.
Extract anything that helps match buy/sell listings:
- Reference / model numbers (e.g. 126334, 116500LN, M228239, 5711/1A)
- Brand if obvious (Rolex, Patek, AP, etc.)
- Any price and currency visible (£, $, €, CHF, USD, GBP, EUR, k for thousands)
- Condition hints (unworn, full set, etc.)
- Manufacturing or warranty-card year: a 4-digit year like 2019 or 2022 on the card is a YEAR, not a model reference. DD.MM.YYYY dates on papers are years/dates, not refs.

Reply with plain text lines only, no markdown. Start each line with a label:
REF: (space-separated candidate references, or NONE)
YEAR: (single 4-digit year from card/tag if visible, or NONE)
BRAND: (or NONE)
PRICE: (or NONE)
NOTES: short free text or NONE
If unreadable, still reply with REF: NONE etc."""


async def extract_watch_text_from_image(
    image_bytes: bytes,
    mime_type: str,
    *,
    caption: str,
) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        log.info("vision_skipped_no_api_key")
        return ""

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_vision_timeout_seconds,
    )
    model = settings.openai_vision_model
    user_lines = _VISION_PROMPT
    if caption.strip():
        user_lines += f"\n\nChat caption (may be empty or partial):\n{caption.strip()}"

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_lines},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        max_tokens=400,
    )
    choice = resp.choices[0].message.content
    out = (choice or "").strip()
    if out:
        log.info("vision_extract_ok", chars=len(out), model=model)
    return out
