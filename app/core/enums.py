"""All explicit enums used across the system."""

from __future__ import annotations

from enum import StrEnum


class MessageClassification(StrEnum):
    SELL_OFFER = "SELL_OFFER"
    BUY_REQUEST = "BUY_REQUEST"
    OTHER = "OTHER"


class ParseMethod(StrEnum):
    RULE = "RULE"
    LLM = "LLM"
    HYBRID = "HYBRID"


class ProcessingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class SourceType(StrEnum):
    WHATSAPP_WEBHOOK = "WHATSAPP_WEBHOOK"
    WHATSAPP_BAILEYS = "WHATSAPP_BAILEYS"
    FAKE = "FAKE"


class GroupType(StrEnum):
    SELLERS = "SELLERS"
    BUYERS = "BUYERS"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class SellOfferStatus(StrEnum):
    ACTIVE = "ACTIVE"
    MATCHED = "MATCHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"


class BuyRequestStatus(StrEnum):
    OPEN = "OPEN"
    OPEN_UNPRICED = "OPEN_UNPRICED"
    MATCHED = "MATCHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    EXPIRED = "EXPIRED"


class MatchType(StrEnum):
    EXACT_REF = "EXACT_REF"
    ALIAS_MATCH = "ALIAS_MATCH"
    FUZZY_REF = "FUZZY_REF"
    FAMILY_MATCH = "FAMILY_MATCH"


class MatchStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class AlertType(StrEnum):
    PROFITABLE_MATCH = "PROFITABLE_MATCH"
    UNPRICED_MATCH = "UNPRICED_MATCH"
    LOW_CONFIDENCE_PARSE = "LOW_CONFIDENCE_PARSE"
    ERROR = "ERROR"


class AlertChannel(StrEnum):
    TELEGRAM = "TELEGRAM"
    DASHBOARD = "DASHBOARD"


class AlertStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


class ReviewTargetType(StrEnum):
    MATCH = "MATCH"
    BUY_REQUEST = "BUY_REQUEST"
    SELL_OFFER = "SELL_OFFER"
    PARSED_MESSAGE = "PARSED_MESSAGE"
    ALERT = "ALERT"


class ReviewActionType(StrEnum):
    APPROVE_MATCH = "APPROVE_MATCH"
    REJECT_MATCH = "REJECT_MATCH"
    MARK_FALSE_PARSE = "MARK_FALSE_PARSE"
    CLOSE_BUY_REQUEST = "CLOSE_BUY_REQUEST"
    CLOSE_SELL_OFFER = "CLOSE_SELL_OFFER"
    SNOOZE_ALERT = "SNOOZE_ALERT"
    ARCHIVE = "ARCHIVE"


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"


class EmbeddingObjectType(StrEnum):
    RAW_MESSAGE = "RAW_MESSAGE"
    PARSED_MESSAGE = "PARSED_MESSAGE"
    WATCH_ENTITY = "WATCH_ENTITY"
    SELL_OFFER = "SELL_OFFER"
    BUY_REQUEST = "BUY_REQUEST"


class AliasType(StrEnum):
    NICKNAME = "NICKNAME"
    SHORTHAND = "SHORTHAND"
    REFERENCE = "REFERENCE"
    MISSPELLING = "MISSPELLING"
    OTHER = "OTHER"


SELL_OFFER_TRANSITIONS: dict[SellOfferStatus, set[SellOfferStatus]] = {
    SellOfferStatus.ACTIVE: {
        SellOfferStatus.MATCHED,
        SellOfferStatus.CLOSED,
        SellOfferStatus.ARCHIVED,
        SellOfferStatus.EXPIRED,
    },
    SellOfferStatus.MATCHED: {SellOfferStatus.CLOSED, SellOfferStatus.ARCHIVED},
    SellOfferStatus.CLOSED: set(),
    SellOfferStatus.ARCHIVED: set(),
    SellOfferStatus.EXPIRED: set(),
}

BUY_REQUEST_TRANSITIONS: dict[BuyRequestStatus, set[BuyRequestStatus]] = {
    BuyRequestStatus.OPEN: {
        BuyRequestStatus.MATCHED,
        BuyRequestStatus.CLOSED,
        BuyRequestStatus.ARCHIVED,
        BuyRequestStatus.EXPIRED,
    },
    BuyRequestStatus.OPEN_UNPRICED: {
        BuyRequestStatus.MATCHED,
        BuyRequestStatus.CLOSED,
        BuyRequestStatus.ARCHIVED,
        BuyRequestStatus.EXPIRED,
        BuyRequestStatus.OPEN,
    },
    BuyRequestStatus.MATCHED: {BuyRequestStatus.CLOSED},
    BuyRequestStatus.CLOSED: set(),
    BuyRequestStatus.ARCHIVED: set(),
    BuyRequestStatus.EXPIRED: set(),
}

MATCH_TRANSITIONS: dict[MatchStatus, set[MatchStatus]] = {
    MatchStatus.PENDING_REVIEW: {MatchStatus.APPROVED, MatchStatus.REJECTED, MatchStatus.EXPIRED},
    MatchStatus.APPROVED: set(),
    MatchStatus.REJECTED: set(),
    MatchStatus.EXPIRED: set(),
}


def can_transition_sell_offer(src: SellOfferStatus, dst: SellOfferStatus) -> bool:
    return dst in SELL_OFFER_TRANSITIONS.get(src, set())


def can_transition_buy_request(src: BuyRequestStatus, dst: BuyRequestStatus) -> bool:
    return dst in BUY_REQUEST_TRANSITIONS.get(src, set())


def can_transition_match(src: MatchStatus, dst: MatchStatus) -> bool:
    return dst in MATCH_TRANSITIONS.get(src, set())
