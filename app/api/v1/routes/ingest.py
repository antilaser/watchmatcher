from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.v1.deps import SessionDep, WorkspaceDep
from app.core.enums import SourceType
from app.core.security import hmac_verify
from app.ingestion.service import IngestionService
from app.models import SourceAccount
from app.schemas.message import WebhookIngestPayload

router = APIRouter(prefix="/ingest", tags=["ingest"])


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
    created, skipped = await ingestion.ingest_batch(workspace, src, payload.messages)
    await session.commit()

    try:
        from app.workers.queue import enqueue_process_raw_message

        for row in created:
            await enqueue_process_raw_message(row.id)
    except Exception:
        pass

    return {
        "accepted": len(payload.messages),
        "created": len(created),
        "skipped": skipped,
        "raw_message_ids": [str(r.id) for r in created],
    }
