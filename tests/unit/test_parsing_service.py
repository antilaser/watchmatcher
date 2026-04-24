from __future__ import annotations

import pytest

from app.core.enums import MessageClassification
from app.parsing.service import ParsingService
from app.schemas.parsing import ExtractedWatchTrade


@pytest.mark.asyncio
async def test_parse_classifies_from_caption_when_vision_pollutes_sell_keywords():
    """Vision text can contain 'for wire' etc.; intent must follow the user caption."""
    svc = ParsingService()
    svc._llm_enabled = False
    caption = "WTB - 218235\nWave dial\nPlz pm me"
    merged = f"{caption}\nNOTES: payment for wire pls"
    r = await svc.parse(
        merged,
        has_image=True,
        classification_text=caption,
        caption_for_reference=caption,
    )
    assert r.classification.classification == MessageClassification.BUY_REQUEST
    assert r.extracted.reference == "218235"


def test_extracted_watch_trade_separates_calendar_year_reference():
    extracted = ExtractedWatchTrade(
        classification=MessageClassification.SELL_OFFER,
        brand="Omega",
        reference="2024",
        confidence=0.8,
    )

    assert extracted.reference is None
    assert extracted.year == 2024
