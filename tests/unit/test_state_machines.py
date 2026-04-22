from __future__ import annotations

from app.core.enums import (
    BuyRequestStatus,
    MatchStatus,
    SellOfferStatus,
    can_transition_buy_request,
    can_transition_match,
    can_transition_sell_offer,
)


def test_offer_transitions():
    assert can_transition_sell_offer(SellOfferStatus.ACTIVE, SellOfferStatus.MATCHED)
    assert can_transition_sell_offer(SellOfferStatus.ACTIVE, SellOfferStatus.CLOSED)
    assert not can_transition_sell_offer(SellOfferStatus.CLOSED, SellOfferStatus.ACTIVE)
    assert not can_transition_sell_offer(SellOfferStatus.EXPIRED, SellOfferStatus.MATCHED)


def test_request_transitions():
    assert can_transition_buy_request(BuyRequestStatus.OPEN_UNPRICED, BuyRequestStatus.MATCHED)
    assert can_transition_buy_request(BuyRequestStatus.OPEN_UNPRICED, BuyRequestStatus.OPEN)
    assert not can_transition_buy_request(BuyRequestStatus.CLOSED, BuyRequestStatus.OPEN)


def test_match_transitions():
    assert can_transition_match(MatchStatus.PENDING_REVIEW, MatchStatus.APPROVED)
    assert can_transition_match(MatchStatus.PENDING_REVIEW, MatchStatus.REJECTED)
    assert not can_transition_match(MatchStatus.APPROVED, MatchStatus.REJECTED)
