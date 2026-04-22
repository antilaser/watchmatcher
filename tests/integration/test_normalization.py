from __future__ import annotations

from pathlib import Path

import pytest

from app.normalization.catalog_loader import load_catalog
from app.normalization.service import NormalizationService
from app.schemas.parsing import ExtractedWatchTrade
from app.core.enums import MessageClassification

SEED = Path(__file__).resolve().parent.parent.parent / "app" / "seed" / "data" / "watch_catalog.json"


@pytest.mark.asyncio
async def test_normalize_exact(session):
    await load_catalog(session, SEED)
    svc = NormalizationService(session)
    result = await svc.normalize(
        ExtractedWatchTrade(
            classification=MessageClassification.SELL_OFFER,
            brand="Rolex",
            reference="126610LV",
        )
    )
    assert result.watch_entity_id is not None
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_normalize_by_alias(session):
    await load_catalog(session, SEED)
    svc = NormalizationService(session)
    result = await svc.normalize(
        ExtractedWatchTrade(
            classification=MessageClassification.SELL_OFFER,
            brand="Rolex",
            nickname="Starbucks",
        )
    )
    assert result.watch_entity_id is not None
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_normalize_unresolved(session):
    svc = NormalizationService(session)
    result = await svc.normalize(
        ExtractedWatchTrade(
            classification=MessageClassification.SELL_OFFER,
            brand="UnknownBrand",
            reference="ZZZ999",
        )
    )
    assert result.watch_entity_id is None
    assert result.reason == "unresolved"
