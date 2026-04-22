"""Seed script — populate workspace, sources, watch catalog, and sample messages."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.enums import SourceType
from app.core.logging import configure_logging, get_logger
from app.ingestion.providers.fake import FakeProvider
from app.ingestion.service import IngestionService
from app.models import SourceAccount, Workspace
from app.normalization.catalog_loader import load_catalog
from app.services.pipeline import PipelineService

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "app" / "seed" / "data"


async def main() -> None:
    configure_logging("INFO")
    log = get_logger(__name__)
    settings = get_settings()

    async with session_scope() as session:
        ws = (
            await session.execute(select(Workspace).where(Workspace.name == settings.default_workspace_name))
        ).scalar_one_or_none()
        if ws is None:
            ws = Workspace(name=settings.default_workspace_name, settings_json={})
            session.add(ws)
            await session.flush()
            log.info("workspace_created", id=str(ws.id))

        src = (
            await session.execute(
                select(SourceAccount).where(
                    SourceAccount.workspace_id == ws.id,
                    SourceAccount.account_name == "fake-seed",
                )
            )
        ).scalar_one_or_none()
        if src is None:
            src = SourceAccount(
                workspace_id=ws.id,
                source_type=SourceType.FAKE,
                account_name="fake-seed",
                status="ACTIVE",
                metadata_json={},
            )
            session.add(src)
            await session.flush()
            log.info("source_account_created", id=str(src.id))

        created = await load_catalog(session, SEED_DIR / "watch_catalog.json")
        log.info("catalog_seeded", new_entities=created)

        provider = FakeProvider.from_json_file(SEED_DIR / "sample_messages.json")
        msgs = await provider.poll_messages()
        ingestion = IngestionService(session)
        rows, skipped = await ingestion.ingest_batch(ws, src, msgs)
        log.info("messages_ingested", created=len(rows), skipped=skipped)

        pipeline = PipelineService(session)
        for r in rows:
            await pipeline.process_raw_message(r.id)

    log.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())
