"""Load watch catalog from JSON seed files into the database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AliasType
from app.core.logging import get_logger
from app.models import WatchEntity, WatchEntityAlias

log = get_logger(__name__)


async def load_catalog(session: AsyncSession, path: str | Path) -> int:
    data: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))
    created = 0
    for entry in data:
        brand = entry["brand"]
        family = entry["family"]
        reference = entry["reference"]

        existing = (
            await session.execute(
                select(WatchEntity).where(
                    WatchEntity.brand == brand,
                    WatchEntity.family == family,
                    WatchEntity.reference == reference,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            entity = WatchEntity(
                brand=brand,
                family=family,
                reference=reference,
                nickname=entry.get("nickname"),
                aliases_json=entry.get("aliases", []),
                metadata_json=entry.get("metadata", {}),
            )
            session.add(entity)
            await session.flush()
            created += 1
        else:
            entity = existing

        for alias in entry.get("aliases", []):
            alias_text = alias["text"] if isinstance(alias, dict) else alias
            alias_type = alias.get("type", AliasType.NICKNAME) if isinstance(alias, dict) else AliasType.NICKNAME
            weight = float(alias.get("weight", 1.0)) if isinstance(alias, dict) else 1.0

            exists = (
                await session.execute(
                    select(WatchEntityAlias).where(
                        WatchEntityAlias.watch_entity_id == entity.id,
                        WatchEntityAlias.alias_text == alias_text,
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    WatchEntityAlias(
                        watch_entity_id=entity.id,
                        alias_text=alias_text,
                        alias_type=alias_type,
                        confidence_weight=weight,
                    )
                )
    await session.flush()
    log.info("watch_catalog_loaded", new_entities=created)
    return created
