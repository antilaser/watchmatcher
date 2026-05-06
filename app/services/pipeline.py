"""End-to-end processing pipeline for a single RawMessage."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.service import AlertService
from app.alerts.search_alarm_service import SearchAlarmService
from app.core.config import get_settings
from app.core.enums import (
    BuyRequestStatus,
    MessageClassification,
    ProcessingStatus,
    SellOfferStatus,
)
from app.core.logging import get_logger
from app.ingestion.media_redis import pop_pending_image
from app.matching.service import MatchingService
from app.models import BuyRequest, Group, ParsedMessage, RawMessage, SellOffer
from app.normalization.service import NormalizationService
from app.parsing.service import ParsingService
from app.parsing.vision_extract import extract_watch_text_from_image
from app.schemas.parsing import ExtractedWatchTrade, ParseResult

log = get_logger(__name__)


def _parse_has_image(raw: RawMessage) -> bool:
    """True when listing should use image/caption sell heuristics (incl. image sent as WhatsApp document)."""
    if raw.message_type in ("image", "video"):
        return True
    meta = raw.metadata_json or {}
    if meta.get("image_sent_as_document"):
        return True
    if raw.message_type == "document":
        mime = meta.get("document_mimetype") or meta.get("image_mime_type")
        if isinstance(mime, str) and mime.lower().startswith("image/"):
            return True
    return False


class PipelineService:
    def __init__(
        self,
        session: AsyncSession,
        parsing: ParsingService | None = None,
        normalization: NormalizationService | None = None,
        matching: MatchingService | None = None,
        alerts: AlertService | None = None,
        search_alarms: SearchAlarmService | None = None,
    ) -> None:
        self.session = session
        self.parsing = parsing or ParsingService()
        self.normalization = normalization or NormalizationService(session)
        self.matching = matching or MatchingService(session)
        self.alerts = alerts or AlertService(session)
        self.search_alarms = search_alarms or SearchAlarmService(session)

    async def process_raw_message(self, raw_message_id: UUID) -> None:
        raw = (
            await self.session.execute(select(RawMessage).where(RawMessage.id == raw_message_id))
        ).scalar_one_or_none()
        if raw is None:
            log.warning("raw_message_not_found", id=str(raw_message_id))
            return

        if raw.processing_status == ProcessingStatus.COMPLETED:
            return

        grp = (
            await self.session.execute(select(Group).where(Group.id == raw.group_id))
        ).scalar_one_or_none()
        if grp is not None and not grp.is_active:
            meta = dict(raw.metadata_json or {})
            meta["skipped_reason"] = "inactive_group"
            raw.metadata_json = meta
            raw.processing_status = ProcessingStatus.COMPLETED
            await self.session.flush()
            log.info(
                "pipeline_skipped_inactive_group",
                raw_message_id=str(raw.id),
                group_id=str(raw.group_id),
            )
            return

        raw.processing_status = ProcessingStatus.PROCESSING
        try:
            settings = get_settings()
            caption_only = (raw.text_body or "").strip()
            text_for_parse = caption_only
            popped = await pop_pending_image(raw.id)
            if popped:
                img_bytes, mime = popped
                if len(img_bytes) > settings.vision_max_image_bytes:
                    log.warning("vision_image_too_large", bytes=len(img_bytes))
                elif settings.vision_enabled and settings.openai_api_key:
                    try:
                        vision_snippet = await extract_watch_text_from_image(
                            img_bytes, mime, caption=text_for_parse
                        )
                        if vision_snippet.strip():
                            glue = "\n" if text_for_parse else ""
                            text_for_parse = (
                                f"{text_for_parse}{glue}{vision_snippet.strip()}"
                            ).strip()
                            meta = dict(raw.metadata_json or {})
                            meta["vision_snippet"] = vision_snippet[:2000]
                            raw.metadata_json = meta
                    except Exception as e:
                        log.warning("vision_extract_failed", error=str(e))
                elif not settings.openai_api_key:
                    log.info("vision_skipped_no_openai_key_after_image_ingest")

            has_img = _parse_has_image(raw)
            cls_text = caption_only if (has_img and caption_only) else None
            parse_result = await self.parsing.parse(
                text_for_parse,
                has_image=has_img,
                classification_text=cls_text,
                caption_for_reference=caption_only if caption_only else None,
            )
            parsed = await self._persist_parsed(raw, parse_result)

            if parse_result.classification.classification == MessageClassification.OTHER:
                raw.processing_status = ProcessingStatus.COMPLETED
                return

            normalization = await self.normalization.normalize(parse_result.extracted)

            if parse_result.classification.classification == MessageClassification.SELL_OFFER:
                offer = await self._create_sell_offer(raw, parsed, parse_result.extracted, normalization)
                await self.search_alarms.check_sell_offer(offer)
                matches = await self.matching.match_for_new_offer(offer)
            else:
                request = await self._create_buy_request(raw, parsed, parse_result.extracted, normalization)
                await self.search_alarms.check_buy_request(request)
                matches = await self.matching.match_for_new_request(request)

            for m in matches:
                await self.alerts.maybe_create_for_match(m)

            raw.processing_status = (
                ProcessingStatus.REVIEW_REQUIRED
                if parse_result.needs_review
                else ProcessingStatus.COMPLETED
            )
        except Exception as e:
            raw.processing_status = ProcessingStatus.FAILED
            raw.processing_error = str(e)
            raw.retry_count += 1
            log.exception("pipeline_failed", raw_message_id=str(raw.id))
            raise

    async def _persist_parsed(self, raw: RawMessage, result: ParseResult) -> ParsedMessage:
        existing = (
            await self.session.execute(
                select(ParsedMessage).where(ParsedMessage.raw_message_id == raw.id)
            )
        ).scalar_one_or_none()
        if existing:
            existing.classification = result.classification.classification
            existing.classification_confidence = result.classification.confidence
            existing.parse_method = result.parse_method
            existing.parse_confidence = result.parse_confidence
            existing.extracted_json = result.extracted.model_dump(mode="json")
            existing.needs_review = result.needs_review
            return existing

        parsed = ParsedMessage(
            raw_message_id=raw.id,
            classification=result.classification.classification,
            classification_confidence=result.classification.confidence,
            parse_method=result.parse_method,
            parse_confidence=result.parse_confidence,
            extracted_json=result.extracted.model_dump(mode="json"),
            needs_review=result.needs_review,
        )
        self.session.add(parsed)
        await self.session.flush()
        return parsed

    async def _create_sell_offer(
        self,
        raw: RawMessage,
        parsed: ParsedMessage,
        extracted: ExtractedWatchTrade,
        normalization,
    ) -> SellOffer:
        offer = SellOffer(
            workspace_id=raw.workspace_id,
            raw_message_id=raw.id,
            parsed_message_id=parsed.id,
            watch_entity_id=normalization.watch_entity_id,
            brand_raw=extracted.brand,
            family_raw=extracted.model_family,
            reference_raw=extracted.reference,
            manufacture_year=extracted.year,
            condition_raw=extracted.condition,
            set_completeness_raw=("full_set" if extracted.full_set else None),
            asking_price=Decimal(str(extracted.price)) if extracted.price else None,
            currency=extracted.currency,
            location_raw=extracted.location,
            seller_name=raw.sender_name,
            notes=extracted.notes,
            extra_json={"normalization_reason": normalization.reason},
            negotiable=bool(extracted.negotiable) if extracted.negotiable is not None else False,
            status=SellOfferStatus.ACTIVE,
            confidence=extracted.confidence,
        )
        self.session.add(offer)
        await self.session.flush()
        return offer

    async def _create_buy_request(
        self,
        raw: RawMessage,
        parsed: ParsedMessage,
        extracted: ExtractedWatchTrade,
        normalization,
    ) -> BuyRequest:
        has_price = extracted.price is not None and extracted.price > 0
        request = BuyRequest(
            workspace_id=raw.workspace_id,
            raw_message_id=raw.id,
            parsed_message_id=parsed.id,
            watch_entity_id=normalization.watch_entity_id,
            brand_raw=extracted.brand,
            family_raw=extracted.model_family,
            reference_raw=extracted.reference,
            condition_raw=extracted.condition,
            target_price=Decimal(str(extracted.price)) if has_price else None,
            currency=extracted.currency,
            location_raw=extracted.location,
            buyer_name=raw.sender_name,
            notes=extracted.notes,
            extra_json={"normalization_reason": normalization.reason},
            status=BuyRequestStatus.OPEN if has_price else BuyRequestStatus.OPEN_UNPRICED,
            confidence=extracted.confidence,
        )
        self.session.add(request)
        await self.session.flush()
        return request


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
