"""Matching service — produces Match rows for newly created offers/requests."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import MatchStatus, MatchType
from app.core.logging import get_logger
from app.matching.candidate_search import (
    find_active_sell_offers_for_request,
    find_open_buy_requests_for_offer,
)
from app.matching.profit import ProfitInputs, calculate_profit
from app.matching.scoring import ScoreInputs, compute_match_score
from app.models import BuyRequest, Match, SellOffer

log = get_logger(__name__)


def _decide_match_type(offer: SellOffer, request: BuyRequest) -> tuple[MatchType, float, float, float]:
    """Return (match_type, reference_score, brand_score, family_score)."""
    same_entity = (
        offer.watch_entity_id is not None
        and offer.watch_entity_id == request.watch_entity_id
    )
    same_ref = (
        offer.reference_raw is not None
        and request.reference_raw is not None
        and offer.reference_raw.upper() == request.reference_raw.upper()
    )
    same_brand = (
        offer.brand_raw is not None
        and request.brand_raw is not None
        and offer.brand_raw.lower() == request.brand_raw.lower()
    )
    same_family = (
        offer.family_raw is not None
        and request.family_raw is not None
        and offer.family_raw.lower() == request.family_raw.lower()
    )

    if same_entity or same_ref:
        return MatchType.EXACT_REF, 1.0, 1.0 if same_brand else 0.7, 1.0 if same_family else 0.6
    if same_brand and same_family:
        return MatchType.FAMILY_MATCH, 0.4, 1.0, 1.0
    if same_brand:
        return MatchType.FUZZY_REF, 0.3, 1.0, 0.4
    return MatchType.FUZZY_REF, 0.2, 0.4, 0.4


class MatchingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._settings = get_settings()

    async def match_for_new_offer(self, offer: SellOffer) -> list[Match]:
        candidates = await find_open_buy_requests_for_offer(self.session, offer)
        return await self._build_matches(offer=offer, requests=candidates)

    async def match_for_new_request(self, request: BuyRequest) -> list[Match]:
        offers = await find_active_sell_offers_for_request(self.session, request)
        return await self._build_matches_for_request(request=request, offers=offers)

    async def _build_matches(
        self,
        offer: SellOffer,
        requests: list[BuyRequest],
    ) -> list[Match]:
        out: list[Match] = []
        for request in requests:
            m = await self._build_or_get_match(offer, request)
            if m is not None:
                out.append(m)
        return out

    async def _build_matches_for_request(
        self,
        request: BuyRequest,
        offers: list[SellOffer],
    ) -> list[Match]:
        out: list[Match] = []
        for offer in offers:
            m = await self._build_or_get_match(offer, request)
            if m is not None:
                out.append(m)
        return out

    async def _build_or_get_match(
        self,
        offer: SellOffer,
        request: BuyRequest,
    ) -> Match | None:
        existing = (
            await self.session.execute(
                select(Match).where(
                    Match.sell_offer_id == offer.id,
                    Match.buy_request_id == request.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        match_type, ref_s, brand_s, fam_s = _decide_match_type(offer, request)
        score = compute_match_score(
            ScoreInputs(
                reference_score=ref_s,
                brand_score=brand_s,
                family_score=fam_s,
                alias_score=0.0,
                parse_confidence=float(min(offer.confidence, request.confidence)),
                offer_created_at=offer.created_at,
                request_created_at=request.created_at,
            )
        )

        profit = calculate_profit(
            ProfitInputs(
                seller_price=offer.asking_price,
                buyer_price=request.target_price,
                seller_currency=offer.currency,
                buyer_currency=request.currency,
                fx_rate=Decimal("1.0") if offer.currency == request.currency else None,
                shipping_cost=Decimal(str(self._settings.default_shipping_cost)),
                fee_percent=Decimal(str(self._settings.default_fee_percent)),
                fixed_fee=Decimal(str(self._settings.default_fixed_fee)),
                risk_buffer=Decimal(str(self._settings.default_risk_buffer)),
            )
        )

        m = Match(
            workspace_id=offer.workspace_id,
            sell_offer_id=offer.id,
            buy_request_id=request.id,
            watch_entity_id=offer.watch_entity_id or request.watch_entity_id,
            match_type=match_type,
            match_confidence=score,
            seller_price=offer.asking_price,
            buyer_price=request.target_price,
            seller_currency=offer.currency,
            buyer_currency=request.currency,
            fx_rate=Decimal("1.0") if offer.currency == request.currency else None,
            shipping_cost=Decimal(str(self._settings.default_shipping_cost)),
            fee_cost=None,
            risk_buffer=Decimal(str(self._settings.default_risk_buffer)),
            expected_profit=profit.expected_profit,
            status=MatchStatus.PENDING_REVIEW,
            reasoning_json={
                "match_type": match_type.value,
                "reference_score": ref_s,
                "brand_score": brand_s,
                "family_score": fam_s,
                "score": score,
                "profit_breakdown": profit.breakdown,
            },
        )
        self.session.add(m)
        await self.session.flush()
        log.info(
            "match_created",
            match_id=str(m.id),
            offer_id=str(offer.id),
            request_id=str(request.id),
            score=score,
            profit=str(profit.expected_profit) if profit.expected_profit is not None else None,
        )
        return m
