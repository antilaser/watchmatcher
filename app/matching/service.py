"""Matching service — produces Match rows for newly created offers/requests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import MatchStatus, MatchType
from app.core.logging import get_logger
from app.matching.calibration import (
    effective_exact_reference_floor,
    effective_match_candidate_max_age_days,
)
from app.matching.candidate_search import (
    find_active_sell_offers_for_request,
    find_open_buy_requests_for_offer,
)
from app.matching.profit import ProfitInputs, ProfitResult, calculate_profit
from app.matching.reporting_fx import build_reporting_amounts_for_profit
from app.matching.scoring import ScoreInputs, compute_match_score
from app.models import BuyRequest, Match, ParsedMessage, RawMessage, SellOffer, Workspace
from app.parsing.year_constraints import extract_min_year

log = get_logger(__name__)

_MIN_REF_PREFIX_LEN = 4


def _refs_compatible(offer_ref: str | None, request_ref: str | None) -> bool:
    """True when refs are equal or one is a meaningful prefix of the other (e.g. 126334 vs 126334-0001)."""
    if not offer_ref or not request_ref:
        return False
    o = str(offer_ref).strip().upper()
    r = str(request_ref).strip().upper()
    if o == r:
        return True
    if len(o) < _MIN_REF_PREFIX_LEN or len(r) < _MIN_REF_PREFIX_LEN:
        return False
    return r.startswith(o) or o.startswith(r)


def _decide_match_type(offer: SellOffer, request: BuyRequest) -> tuple[MatchType, float, float, float]:
    """Return (match_type, reference_score, brand_score, family_score)."""
    same_entity = (
        offer.watch_entity_id is not None
        and offer.watch_entity_id == request.watch_entity_id
    )
    same_ref = _refs_compatible(offer.reference_raw, request.reference_raw)
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

    async def _counterpart_message_cutoff(self, workspace_id: UUID) -> datetime:
        ws = (
            await self.session.execute(select(Workspace).where(Workspace.id == workspace_id))
        ).scalar_one_or_none()
        days = effective_match_candidate_max_age_days(self._settings, ws)
        return datetime.now(timezone.utc) - timedelta(days=days)

    async def _request_min_year(self, request: BuyRequest) -> int | None:
        row = (
            await self.session.execute(
                select(RawMessage.text_body, ParsedMessage.extracted_json)
                .join(ParsedMessage, ParsedMessage.raw_message_id == RawMessage.id)
                .where(RawMessage.id == request.raw_message_id)
            )
        ).one_or_none()
        if row is None:
            return None
        text_body, extracted = row
        year = extract_min_year(text_body)
        if year is None:
            return None
        parsed_year = (extracted or {}).get("year")
        if isinstance(parsed_year, int) and parsed_year != year:
            return None
        return year

    async def match_for_new_offer(self, offer: SellOffer) -> list[Match]:
        cutoff = await self._counterpart_message_cutoff(offer.workspace_id)
        candidates = await find_open_buy_requests_for_offer(
            self.session,
            offer,
            counterpart_message_not_before=cutoff,
        )
        return await self._build_matches(offer=offer, requests=candidates)

    async def match_for_new_request(self, request: BuyRequest) -> list[Match]:
        cutoff = await self._counterpart_message_cutoff(request.workspace_id)
        offers = await find_active_sell_offers_for_request(
            self.session,
            request,
            counterpart_message_not_before=cutoff,
        )
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

        min_year = await self._request_min_year(request)
        if (
            min_year is not None
            and offer.manufacture_year is not None
            and offer.manufacture_year < min_year
        ):
            log.info(
                "match_skipped_offer_too_old",
                offer_id=str(offer.id),
                request_id=str(request.id),
                offer_year=offer.manufacture_year,
                request_min_year=min_year,
            )
            return None

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
        exact_ref = (
            offer.reference_raw
            and request.reference_raw
            and str(offer.reference_raw).strip().upper() == str(request.reference_raw).strip().upper()
            and len(str(offer.reference_raw).strip()) >= 4
        )
        if exact_ref:
            ws = (
                await self.session.execute(
                    select(Workspace).where(Workspace.id == offer.workspace_id)
                )
            ).scalar_one_or_none()
            floor = effective_exact_reference_floor(self._settings, ws)
            score = max(score, floor)

        ship = Decimal(str(self._settings.default_shipping_cost))
        fee_p = Decimal(str(self._settings.default_fee_percent))
        fee_f = Decimal(str(self._settings.default_fixed_fee))
        risk = Decimal(str(self._settings.default_risk_buffer))

        if offer.asking_price is not None and request.target_price is not None:
            async with httpx.AsyncClient(timeout=25.0) as http:
                rep = await build_reporting_amounts_for_profit(
                    offer=offer,
                    request=request,
                    settings=self._settings,
                    http=http,
                )
            if rep is not None:
                profit = calculate_profit(
                    ProfitInputs(
                        seller_price=rep.seller,
                        buyer_price=rep.buyer,
                        seller_currency=rep.profit_currency,
                        buyer_currency=rep.profit_currency,
                        fx_rate=None,
                        shipping_cost=ship,
                        fee_percent=fee_p,
                        fixed_fee=fee_f,
                        risk_buffer=risk,
                    )
                )
                profit_breakdown = {**profit.breakdown, "fx_conversion": rep.fx_meta}
            else:
                profit = ProfitResult(
                    expected_profit=None,
                    seller_price_base=offer.asking_price,
                    buyer_price_base=request.target_price,
                    fx_applied=False,
                    breakdown={
                        "reason": "reporting_currency_conversion_unavailable",
                        "hint": "Configure XE_ACCOUNT_ID and XE_API_KEY (Xe Currency Data API), or set PROFIT_REPORTING_CURRENCY=AUTO when both legs share the same currency.",
                        "seller_currency": offer.currency,
                        "buyer_currency": request.currency,
                    },
                )
                profit_breakdown = profit.breakdown
        else:
            profit = calculate_profit(
                ProfitInputs(
                    seller_price=offer.asking_price,
                    buyer_price=request.target_price,
                    seller_currency=offer.currency,
                    buyer_currency=request.currency,
                    fx_rate=Decimal("1.0") if offer.currency == request.currency else None,
                    shipping_cost=ship,
                    fee_percent=fee_p,
                    fixed_fee=fee_f,
                    risk_buffer=risk,
                )
            )
            profit_breakdown = profit.breakdown

        match_fx_rate = (
            Decimal("1.0")
            if offer.asking_price is not None
            and request.target_price is not None
            and (offer.currency or "").strip().upper() == (request.currency or "").strip().upper()
            else None
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
            fx_rate=match_fx_rate,
            shipping_cost=ship,
            fee_cost=None,
            risk_buffer=risk,
            expected_profit=profit.expected_profit,
            status=MatchStatus.PENDING_REVIEW,
            reasoning_json={
                "match_type": match_type.value,
                "reference_score": ref_s,
                "brand_score": brand_s,
                "family_score": fam_s,
                "score": score,
                "exact_reference_string_match": exact_ref,
                "profit_breakdown": profit_breakdown,
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
