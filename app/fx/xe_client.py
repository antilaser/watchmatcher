"""Xe Currency Data API (xecdapi.xe.com) — mid-market conversion for profit display."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

XE_API_BASE = "https://xecdapi.xe.com/v1"

# cache: (from_iso, to_iso) -> (converted_amount_for_one_unit_of_from, expires_at_epoch)
_cache: dict[tuple[str, str], tuple[Decimal, float]] = {}
_CACHE_TTL_SEC = 15 * 60


@dataclass
class XeConvertMeta:
    from_currency: str
    to_currency: str
    amount_from: Decimal
    amount_to: Decimal
    rate_implied: Decimal  # amount_to / amount_from
    provider: str = "xe.com"

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
            "amount_from": str(self.amount_from),
            "amount_to": str(self.amount_to),
            "implied_rate": str(self.rate_implied),
            "provider": self.provider,
        }


def _parse_convert_from_response(data: dict[str, Any], to_iso: str) -> Decimal | None:
    """Extract converted counter amount for the target currency from XE convert_from.json."""
    to_iso = to_iso.upper()
    rows = data.get("to")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        q = str(row.get("quotecurrency", "")).upper()
        if q != to_iso:
            continue
        mid = row.get("mid")
        if mid is None:
            return None
        try:
            return Decimal(str(mid))
        except Exception:
            return None
    return None


async def xe_convert(
    amount: Decimal,
    from_iso: str,
    to_iso: str,
    *,
    account_id: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> XeConvertMeta | None:
    """Convert ``amount`` of ``from_iso`` to ``to_iso`` using XE mid rates.

    Uses amount=1 internally for cache hits when only the implied rate is needed;
    callers may pass any positive amount for a live conversion.
    """
    from_u = from_iso.strip().upper()
    to_u = to_iso.strip().upper()
    if from_u == to_u:
        return XeConvertMeta(
            from_currency=from_u,
            to_currency=to_u,
            amount_from=amount,
            amount_to=amount,
            rate_implied=Decimal("1"),
        )

    url = f"{XE_API_BASE}/convert_from.json"
    params = {"from": from_u, "to": to_u, "amount": str(amount)}

    try:
        r = await client.get(url, params=params, auth=(account_id, api_key))
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("xe_convert_request_failed", from_=from_u, to=to_u, error=str(e))
        return None

    conv = _parse_convert_from_response(data, to_u)
    if conv is None:
        log.warning("xe_convert_parse_failed", from_=from_u, to=to_u, body_keys=list(data.keys()))
        return None

    rate = (conv / amount) if amount != 0 else Decimal("0")
    return XeConvertMeta(
        from_currency=from_u,
        to_currency=to_u,
        amount_from=amount,
        amount_to=conv.quantize(Decimal("0.01")),
        rate_implied=rate.quantize(Decimal("0.000001")),
    )


async def xe_rate_via_cache(
    from_iso: str,
    to_iso: str,
    *,
    account_id: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> XeConvertMeta | None:
    """Xe conversion for 1 unit of ``from_iso`` with short-lived RAM cache."""
    from_u = from_iso.strip().upper()
    to_u = to_iso.strip().upper()
    if from_u == to_u:
        return XeConvertMeta(
            from_currency=from_u,
            to_currency=to_u,
            amount_from=Decimal("1"),
            amount_to=Decimal("1"),
            rate_implied=Decimal("1"),
        )

    key = (from_u, to_u)
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and hit[1] > now:
        amt_to = hit[0]
        return XeConvertMeta(
            from_currency=from_u,
            to_currency=to_u,
            amount_from=Decimal("1"),
            amount_to=amt_to,
            rate_implied=amt_to.quantize(Decimal("0.000001")),
        )

    meta = await xe_convert(Decimal("1"), from_u, to_u, account_id=account_id, api_key=api_key, client=client)
    if meta is None:
        return None
    _cache[key] = (meta.amount_to, now + _CACHE_TTL_SEC)
    return meta
