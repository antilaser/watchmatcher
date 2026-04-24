"""Browse sell offers across all groups with filters."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import and_, func, select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import SellOfferStatus
from app.models import Group, RawMessage, SellOffer
from app.schemas.common import Page
from app.schemas.offer import SellListingOut, SellOfferOut

router = APIRouter(prefix="/listings", tags=["listings"])


def _utc_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _utc_day_after(d: date) -> datetime:
    return _utc_start(d + timedelta(days=1))


def _listing_where(
    workspace_id,
    *,
    status_filter: SellOfferStatus | None,
    brand: str | None,
    reference: str | None,
    price_min: Decimal | None,
    price_max: Decimal | None,
    currency: str | None,
    message_on_or_after: date | None,
    message_on_or_before: date | None,
    year: int | None,
    year_min: int | None,
    year_max: int | None,
):
    clauses = [
        SellOffer.workspace_id == workspace_id,
        Group.workspace_id == workspace_id,
    ]
    if status_filter is not None:
        clauses.append(SellOffer.status == status_filter)
    if brand:
        b = brand.strip()[:128]
        clauses.append(SellOffer.brand_raw.isnot(None))
        clauses.append(SellOffer.brand_raw.contains(b, autoescape=True))
    if reference:
        r = reference.strip()[:64]
        clauses.append(SellOffer.reference_raw.isnot(None))
        clauses.append(SellOffer.reference_raw.contains(r, autoescape=True))
    if price_min is not None:
        clauses.append(SellOffer.asking_price.isnot(None))
        clauses.append(SellOffer.asking_price >= price_min)
    if price_max is not None:
        clauses.append(SellOffer.asking_price.isnot(None))
        clauses.append(SellOffer.asking_price <= price_max)
    if currency:
        c = currency.strip().upper()[:8]
        clauses.append(SellOffer.currency == c)
    if message_on_or_after is not None:
        clauses.append(RawMessage.original_timestamp >= _utc_start(message_on_or_after))
    if message_on_or_before is not None:
        clauses.append(RawMessage.original_timestamp < _utc_day_after(message_on_or_before))
    if year is not None:
        clauses.append(SellOffer.manufacture_year == year)
    if year_min is not None:
        clauses.append(SellOffer.manufacture_year.isnot(None))
        clauses.append(SellOffer.manufacture_year >= year_min)
    if year_max is not None:
        clauses.append(SellOffer.manufacture_year.isnot(None))
        clauses.append(SellOffer.manufacture_year <= year_max)
    return and_(*clauses)


def _to_listing_out(
    offer: SellOffer,
    group_name: str,
    message_at: datetime,
    text_body: str | None,
) -> SellListingOut:
    base = SellOfferOut.model_validate(offer).model_dump()
    preview = (text_body or "").replace("\r\n", "\n").strip()
    if len(preview) > 400:
        preview = preview[:400] + "…"
    return SellListingOut(
        **base,
        group_name=group_name,
        message_at=message_at,
        text_preview=preview or None,
    )


@router.get("/sell-offers", response_model=Page[SellListingOut])
async def list_sell_listings(
    workspace: WorkspaceDep,
    session: SessionDep,
    status: SellOfferStatus | None = Query(
        default=None,
        description="Offer status (e.g. ACTIVE). If omitted, all statuses are included.",
    ),
    brand: str | None = Query(default=None, max_length=128),
    reference: str | None = Query(default=None, max_length=64, description="Reference / model number substring"),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    currency: str | None = Query(default=None, max_length=8),
    message_on_or_after: date | None = Query(
        default=None,
        description="WhatsApp message date (UTC day start), inclusive",
    ),
    message_on_or_before: date | None = Query(
        default=None,
        description="WhatsApp message date (UTC day end), inclusive",
    ),
    year: int | None = Query(
        default=None,
        ge=1900,
        le=2099,
        description="Manufacturing / warranty-card year extracted from text or DD.MM.YYYY dates",
    ),
    year_min: int | None = Query(default=None, ge=1900, le=2099),
    year_max: int | None = Query(default=None, ge=1900, le=2099),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """All sell offers from every group, filterable by brand, reference, price, currency, and message date."""
    where_clause = _listing_where(
        workspace.id,
        status_filter=status,
        brand=brand,
        reference=reference,
        price_min=price_min,
        price_max=price_max,
        currency=currency,
        message_on_or_after=message_on_or_after,
        message_on_or_before=message_on_or_before,
        year=year,
        year_min=year_min,
        year_max=year_max,
    )

    base_join = (
        select(SellOffer, Group.group_name, RawMessage.original_timestamp, RawMessage.text_body)
        .join(RawMessage, RawMessage.id == SellOffer.raw_message_id)
        .join(Group, Group.id == RawMessage.group_id)
        .where(where_clause)
    )

    count_stmt = (
        select(func.count(SellOffer.id))
        .select_from(SellOffer)
        .join(RawMessage, RawMessage.id == SellOffer.raw_message_id)
        .join(Group, Group.id == RawMessage.group_id)
        .where(where_clause)
    )
    total = int((await session.execute(count_stmt)).scalar_one())

    rows = (
        await session.execute(
            base_join.order_by(RawMessage.original_timestamp.desc()).limit(limit).offset(offset)
        )
    ).all()

    items = [_to_listing_out(o, gn, ts, tb) for o, gn, ts, tb in rows]
    return Page[SellListingOut](items=items, total=total, limit=limit, offset=offset)
