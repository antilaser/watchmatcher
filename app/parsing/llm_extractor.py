"""LLM-based extraction fallback (OpenAI). Strict JSON output validated by Pydantic."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.parsing import ExtractedWatchTrade

log = get_logger(__name__)


PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are an information extraction engine for second-hand luxury watch trading messages.
You receive a single short message in any language and must return STRICT JSON
matching the schema. Do not include any prose, only valid JSON.

Allowed `classification` values: SELL_OFFER, BUY_REQUEST, OTHER.
If unsure, set fields to null. Do not invent prices or references.
Currency must be ISO-like: EUR, USD, GBP, CHF, JPY, AED.

Schema keys (all optional except `classification`):
- classification (string, required)
- brand (string|null) — canonical brand name e.g. "Rolex"
- model_family (string|null) — e.g. "Submariner Date"
- reference (string|null) — e.g. "126610LV"
- nickname (string|null) — e.g. "Starbucks"
- condition (string|null) — one of: new, mint, excellent, good, worn
- full_set (boolean|null)
- year (integer|null)
- price (number|null)
- currency (string|null)
- negotiable (boolean|null)
- location (string|null)
- notes (string|null)
- confidence (number 0..1)
"""

USER_TEMPLATE = """Message:
\"\"\"{text}\"\"\"

Return ONLY a single JSON object. No commentary."""


class LLMExtractorError(RuntimeError):
    pass


class LLMExtractor:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._settings = get_settings()

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._settings.openai_api_key:
            raise LLMExtractorError("OPENAI_API_KEY not configured")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            timeout=self._settings.openai_timeout_seconds,
        )
        return self._client

    async def extract(self, text: str) -> ExtractedWatchTrade:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(text=text)},
                ],
                temperature=0.0,
            )
        except Exception as e:
            raise LLMExtractorError(f"LLM call failed: {e}") from e

        try:
            content = response.choices[0].message.content
            data = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError, AttributeError) as e:
            raise LLMExtractorError(f"LLM returned invalid JSON: {e}") from e

        try:
            return ExtractedWatchTrade(**data)
        except ValidationError as e:
            log.warning("llm_extract_validation_error", error=str(e), raw=data)
            raise LLMExtractorError(f"LLM JSON failed validation: {e}") from e
