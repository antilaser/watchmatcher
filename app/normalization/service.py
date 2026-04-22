"""Resolve extracted watch fields to a canonical `WatchEntity`.

Pipeline: exact ref -> alias lookup -> fuzzy ref -> family fallback -> review.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import WatchEntity, WatchEntityAlias
from app.normalization.similarity import reference_similarity, token_set_ratio
from app.schemas.parsing import ExtractedWatchTrade

log = get_logger(__name__)


@dataclass
class NormalizationResult:
    watch_entity_id: UUID | None
    canonical_brand: str | None
    canonical_family: str | None
    canonical_reference: str | None
    confidence: float
    reason: str


class NormalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def normalize(self, extracted: ExtractedWatchTrade) -> NormalizationResult:
        if extracted.reference and extracted.brand:
            exact = await self._lookup_exact(extracted.brand, extracted.reference)
            if exact:
                return self._result(exact, 1.0, "exact_brand_reference")

        if extracted.reference:
            ref_only = await self._lookup_by_reference(extracted.reference)
            if ref_only:
                return self._result(ref_only, 0.92, "exact_reference_only")

        if extracted.nickname:
            alias_hit = await self._lookup_by_alias(extracted.nickname)
            if alias_hit:
                entity, weight = alias_hit
                return self._result(entity, min(0.95, 0.7 + 0.25 * float(weight)), "nickname_alias")

        if extracted.reference:
            fuzzy = await self._lookup_fuzzy_reference(extracted.reference)
            if fuzzy:
                entity, score = fuzzy
                return self._result(entity, score, "fuzzy_reference")

        if extracted.brand and extracted.model_family:
            family_hit = await self._lookup_family(extracted.brand, extracted.model_family)
            if family_hit:
                entity, score = family_hit
                return self._result(entity, score, "family_fallback")

        return NormalizationResult(
            watch_entity_id=None,
            canonical_brand=extracted.brand,
            canonical_family=extracted.model_family,
            canonical_reference=extracted.reference,
            confidence=0.0,
            reason="unresolved",
        )

    @staticmethod
    def _result(entity: WatchEntity, confidence: float, reason: str) -> NormalizationResult:
        return NormalizationResult(
            watch_entity_id=entity.id,
            canonical_brand=entity.brand,
            canonical_family=entity.family,
            canonical_reference=entity.reference,
            confidence=confidence,
            reason=reason,
        )

    async def _lookup_exact(self, brand: str, reference: str) -> WatchEntity | None:
        stmt = select(WatchEntity).where(
            WatchEntity.brand == brand,
            WatchEntity.reference.ilike(reference),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _lookup_by_reference(self, reference: str) -> WatchEntity | None:
        stmt = select(WatchEntity).where(WatchEntity.reference.ilike(reference))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _lookup_by_alias(self, alias_text: str) -> tuple[WatchEntity, float] | None:
        stmt = (
            select(WatchEntityAlias, WatchEntity)
            .join(WatchEntity, WatchEntity.id == WatchEntityAlias.watch_entity_id)
            .where(WatchEntityAlias.alias_text.ilike(alias_text))
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        alias, entity = row
        return entity, float(alias.confidence_weight)

    async def _lookup_fuzzy_reference(
        self,
        reference: str,
        threshold: float = 0.85,
    ) -> tuple[WatchEntity, float] | None:
        stmt = select(WatchEntity)
        candidates = (await self.session.execute(stmt)).scalars().all()
        best: tuple[WatchEntity, float] | None = None
        for c in candidates:
            score = reference_similarity(reference, c.reference)
            if score >= threshold and (best is None or score > best[1]):
                best = (c, score)
        if best is None:
            return None
        return best[0], min(0.9, 0.5 + best[1] * 0.4)

    async def _lookup_family(
        self,
        brand: str,
        family: str,
        threshold: float = 0.8,
    ) -> tuple[WatchEntity, float] | None:
        stmt = select(WatchEntity).where(WatchEntity.brand == brand)
        candidates = (await self.session.execute(stmt)).scalars().all()
        best: tuple[WatchEntity, float] | None = None
        for c in candidates:
            score = token_set_ratio(family, c.family)
            if score >= threshold and (best is None or score > best[1]):
                best = (c, score)
        if best is None:
            return None
        return best[0], min(0.7, 0.4 + best[1] * 0.3)
