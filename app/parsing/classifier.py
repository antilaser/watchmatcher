"""Rule-based message classifier."""

from __future__ import annotations

from app.core.enums import MessageClassification
from app.parsing.dictionaries import BUY_KEYWORDS, SELL_KEYWORDS
from app.schemas.parsing import ClassificationResult


def _has_any(text_lower: str, terms: list[str]) -> int:
    return sum(1 for t in terms if t in text_lower)


def classify(text: str) -> ClassificationResult:
    """Heuristic classifier based on keyword counts.

    Confidence reflects strength of signal. Even when both classes match,
    we pick the stronger one but lower confidence.
    """
    if not text or not text.strip():
        return ClassificationResult(
            classification=MessageClassification.OTHER,
            confidence=0.99,
            reason="empty",
        )

    t = text.lower()
    sell_hits = _has_any(t, SELL_KEYWORDS)
    buy_hits = _has_any(t, BUY_KEYWORDS)

    if sell_hits == 0 and buy_hits == 0:
        return ClassificationResult(
            classification=MessageClassification.OTHER,
            confidence=0.6,
            reason="no_keywords",
        )

    if sell_hits > buy_hits:
        confidence = min(0.95, 0.6 + 0.1 * sell_hits - 0.1 * buy_hits)
        return ClassificationResult(
            classification=MessageClassification.SELL_OFFER,
            confidence=max(0.5, confidence),
            reason=f"sell_hits={sell_hits},buy_hits={buy_hits}",
        )
    if buy_hits > sell_hits:
        confidence = min(0.95, 0.6 + 0.1 * buy_hits - 0.1 * sell_hits)
        return ClassificationResult(
            classification=MessageClassification.BUY_REQUEST,
            confidence=max(0.5, confidence),
            reason=f"buy_hits={buy_hits},sell_hits={sell_hits}",
        )

    return ClassificationResult(
        classification=MessageClassification.OTHER,
        confidence=0.4,
        reason=f"tie sell={sell_hits} buy={buy_hits}",
    )
