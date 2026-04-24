from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.enums import SourceType
from app.core.security import hmac_verify
from app.ingestion.service import IngestionService
from app.models import SourceAccount
from app.schemas.message import WebhookIngestPayload

router = APIRouter(prefix="/ingest", tags=["ingest"])
log = get_logger(__name__)


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook_ingest(
    request: Request,
    workspace: WorkspaceDep,
    session: SessionDep,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw_body = await request.body()
    if not x_signature or not hmac_verify(raw_body, x_signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")

    payload = WebhookIngestPayload.model_validate_json(raw_body)

    src_stmt = select(SourceAccount).where(
        SourceAccount.workspace_id == workspace.id,
        SourceAccount.account_name == payload.source_account,
    )
    src = (await session.execute(src_stmt)).scalar_one_or_none()
    if src is None:
        src = SourceAccount(
            workspace_id=workspace.id,
            source_type=SourceType.WHATSAPP_WEBHOOK,
            account_name=payload.source_account,
            status="ACTIVE",
            metadata_json={},
        )
        session.add(src)
        await session.flush()

    ingestion = IngestionService(session)
    created, skipped_dupes, skipped_inactive, pending_images = await ingestion.ingest_batch(
        workspace, src, payload.messages
    )
    await session.commit()

    if pending_images:
        from app.ingestion.media_redis import store_pending_image

        settings = get_settings()
        if settings.vision_enabled and settings.openai_api_key:
            for rid, b64, mime in pending_images:
                try:
                    await store_pending_image(
                        rid, image_base64=b64, image_mime_type=mime
                    )
                except Exception:
                    log.exception("store_pending_image_failed", raw_message_id=str(rid))
        else:
            log.info(
                "vision_images_skipped",
                count=len(pending_images),
                reason="vision_disabled_or_no_openai_key",
            )

    try:
        from app.workers.queue import enqueue_process_raw_message

        for row in created:
            await enqueue_process_raw_message(row.id)
    except Exception:
        log.exception(
            "enqueue_process_raw_message_failed",
            created_count=len(created),
        )

    return {
        "accepted": len(payload.messages),
        "created": len(created),
        "skipped_duplicates": skipped_dupes,
        "skipped_inactive_groups": skipped_inactive,
        "skipped": skipped_dupes + skipped_inactive,
        "raw_message_ids": [str(r.id) for r in created],
    }
