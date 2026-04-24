"""Rule-based message classifier."""

from __future__ import annotations

import re

from app.core.enums import MessageClassification
from app.parsing.dictionaries import BUY_KEYWORDS, SELL_KEYWORDS
from app.parsing.rules import extract_price_and_currency, extract_reference
from app.schemas.parsing import ClassificationResult


def _has_any(text_lower: str, terms: list[str]) -> int:
    return sum(1 for t in terms if t in text_lower)


def _media_caption_looks_priced_listing(text: str) -> bool:
    """Image listing: anchored price, or bare tail amount + ref (e.g. full stickers 22500)."""
    price, currency = extract_price_and_currency(text)
    if price is None:
        return False
    if currency is not None:
        return True
    return extract_reference(text.strip()) is not None


def classify(text: str, *, has_image: bool = False) -> ClassificationResult:
    """Heuristic classifier based on keyword counts.

    Confidence reflects strength of signal. Even when both classes match,
    we pick the stronger one but lower confidence.

    When there are no buy/sell intent keywords, a WhatsApp-style media listing
    (image or video + caption with a real price) is treated as a sell offer.
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
    stripped = text.strip()
    # WTB (want to buy) — word token only, not substring inside other words.
    if re.search(r"(?i)\bwtb\b", stripped):
        buy_hits += 1
    # Shorthand / multilingual one-token or tight phrases (word boundaries).
    if buy_hits == 0 and any(
        re.search(p, stripped)
        for p in (
            r"(?i)\bwlf\b",
            r"(?i)\blf\b",
            r"(?i)\bwtbn\b",
            r"(?i)\bin\s+the\s+market\b",
            r"(?i)\bwho\s+(?:has|got)\b",
            r"(?i)\b(?:i|we)\s+need\b",
            r"(?i)\b(?:ich|wir)\s+suche",
            r"(?i)\b(?:ich|wir)\s+suchen\b",
            r"(?i)\bje\s+cherche\b",
            r"(?i)\brecherche\b",
            r"(?i)\bprocuro\b",
        )
    ):
        buy_hits = 1
    # "Buy M228239 ..." at start of caption (no leading space before "Buy")
    if buy_hits == 0 and re.match(r"(?i)buy\s+[A-Za-z0-9./-]", stripped):
        buy_hits = 1
    if buy_hits == 0 and re.search(r"(?i)\b(?:i\s*am|i'm|im)\s+buying\b", stripped):
        buy_hits = 1
    # Short WhatsApp sells: "sell 126331" (avoid substring "sell " inside "resell …")
    if sell_hits == 0 and re.match(r"(?i)^\s*sell\s+", stripped):
        sell_hits = 1
    if sell_hits == 0 and re.search(r"(?i)\bsell\s+offer\b", stripped):
        sell_hits = 1
    # NTQ = need quote / RFQ (buy). Word-boundary anywhere so "📷 NTQ 5167a" works; do not use a
    # padded " ntq " sell substring — that misfires after emoji/space before NTQ.
    if re.search(r"(?i)\bntq\b", stripped):
        wire_cues = ("for wire", "wire pls", "wire 🔌", "wts", "fs ", "for sale", "asking")
        if not any(c in t for c in wire_cues):
            buy_hits += 1
    # "Any 116518LN …" — first token after "Any" is a reference (common in trading groups).
    if buy_hits == 0:
        m_any = re.match(r"(?i)^\s*any\s+(\S+)", stripped)
        if m_any and extract_reference(m_any.group(1)):
            buy_hits = 1

    if sell_hits == 0 and buy_hits == 0:
        if has_image and _media_caption_looks_priced_listing(text):
            return ClassificationResult(
                classification=MessageClassification.SELL_OFFER,
                confidence=0.64,
                reason="image_caption_price_no_intent_keywords",
            )
        # Photo-only listing: vision may yield REF / card text without a parseable price.
        if has_image and extract_reference(text):
            return ClassificationResult(
                classification=MessageClassification.SELL_OFFER,
                confidence=0.55,
                reason="image_ref_no_price_no_intent_keywords",
            )
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
