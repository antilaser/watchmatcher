"""High-level parsing service: classify + extract + decide LLM fallback."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.enums import MessageClassification, ParseMethod
from app.core.logging import get_logger
from app.parsing.classifier import classify
from app.parsing.llm_extractor import LLMExtractor, LLMExtractorError
from app.parsing.rules import (
    extract_brand,
    extract_condition,
    extract_price_and_currency,
    extract_reference,
    extract_set_completeness,
    extract_year,
    is_negotiable,
)
from app.schemas.parsing import (
    ClassificationResult,
    ExtractedWatchTrade,
    ParseResult,
)

log = get_logger(__name__)


def _rule_extract(
    text: str,
    classification: MessageClassification,
) -> tuple[ExtractedWatchTrade, float]:
    brand = extract_brand(text)
    reference = extract_reference(text)
    price, currency = extract_price_and_currency(text)
    condition = extract_condition(text)
    full_set_str = extract_set_completeness(text)
    year = extract_year(text)
    negotiable = is_negotiable(text)

    score_components: list[float] = []
    if brand:
        score_components.append(0.30)
    if reference:
        score_components.append(0.40)
    if price:
        score_components.append(0.20)
    if condition:
        score_components.append(0.05)
    if full_set_str:
        score_components.append(0.05)

    confidence = sum(score_components)
    extracted = ExtractedWatchTrade(
        classification=classification,
        brand=brand,
        reference=reference,
        price=price,
        currency=currency,
        condition=condition,
        full_set=full_set_str == "full_set" if full_set_str else None,
        year=year,
        negotiable=negotiable,
        confidence=min(1.0, confidence),
    )
    return extracted, confidence


class ParsingService:
    def __init__(self, llm_extractor: LLMExtractor | None = None) -> None:
        settings = get_settings()
        self._llm = llm_extractor or LLMExtractor()
        self._llm_enabled = settings.llm_enabled and settings.llm_fallback_enabled
        self._threshold = settings.rule_parse_confidence_threshold

    async def parse(self, text: str) -> ParseResult:
        cls: ClassificationResult = classify(text)

        if cls.classification == MessageClassification.OTHER:
            return ParseResult(
                classification=cls,
                extracted=ExtractedWatchTrade(classification=cls.classification),
                parse_method=ParseMethod.RULE,
                parse_confidence=cls.confidence,
                needs_review=False,
                notes=["classified_as_other"],
            )

        rule_extracted, rule_conf = _rule_extract(text, cls.classification)

        if rule_conf >= self._threshold or not self._llm_enabled:
            needs_review = rule_conf < self._threshold
            return ParseResult(
                classification=cls,
                extracted=rule_extracted,
                parse_method=ParseMethod.RULE,
                parse_confidence=rule_conf,
                needs_review=needs_review,
            )

        try:
            llm_extracted = await self._llm.extract(text)
        except LLMExtractorError as e:
            log.warning("llm_extract_failed", error=str(e))
            return ParseResult(
                classification=cls,
                extracted=rule_extracted,
                parse_method=ParseMethod.RULE,
                parse_confidence=rule_conf,
                needs_review=True,
                notes=[f"llm_failed: {e}"],
            )

        merged = _merge(rule_extracted, llm_extracted)
        merged_conf = max(rule_conf, llm_extracted.confidence)
        return ParseResult(
            classification=cls,
            extracted=merged,
            parse_method=ParseMethod.HYBRID,
            parse_confidence=merged_conf,
            needs_review=merged_conf < self._threshold,
        )


def _merge(rule: ExtractedWatchTrade, llm: ExtractedWatchTrade) -> ExtractedWatchTrade:
    """Prefer deterministic rule values when present, fall back to LLM otherwise."""
    return ExtractedWatchTrade(
        classification=rule.classification or llm.classification,
        brand=rule.brand or llm.brand,
        model_family=rule.model_family or llm.model_family,
        reference=rule.reference or llm.reference,
        nickname=llm.nickname or rule.nickname,
        condition=rule.condition or llm.condition,
        full_set=rule.full_set if rule.full_set is not None else llm.full_set,
        year=rule.year or llm.year,
        price=rule.price or llm.price,
        currency=rule.currency or llm.currency,
        negotiable=rule.negotiable if rule.negotiable is not None else llm.negotiable,
        location=llm.location or rule.location,
        notes=llm.notes or rule.notes,
        confidence=max(rule.confidence, llm.confidence),
    )
