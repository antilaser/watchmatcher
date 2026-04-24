from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ProcessingStatus


class IncomingMessage(BaseModel):
    """Provider-agnostic incoming message envelope."""

    model_config = ConfigDict(extra="forbid")

    external_message_id: str | None = None
    external_group_id: str
    group_name: str | None = None
    group_invite_code: str | None = None
    sender_name: str | None = None
    sender_external_id: str | None = None
    text_body: str = ""
    message_type: str = "text"
    original_timestamp: datetime
    metadata: dict = Field(default_factory=dict)
    image_base64: str | None = None
    image_mime_type: str | None = Field(default=None, description="e.g. image/jpeg")

    @model_validator(mode="after")
    def _text_or_image(self) -> IncomingMessage:
        has_text = bool(self.text_body and self.text_body.strip())
        has_img = bool(self.image_base64 and self.image_base64.strip())
        if not has_text and not has_img:
            raise ValueError("IncomingMessage requires non-empty text_body or image_base64")
        return self


class WebhookIngestPayload(BaseModel):
    """Payload accepted by `/ingest/webhook`."""

    source_account: str = Field(description="account_name of pre-registered SourceAccount")
    messages: list[IncomingMessage]


class RawMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    group_id: UUID
    external_message_id: str | None
    sender_name: str | None
    text_body: str
    original_timestamp: datetime
    ingested_at: datetime
    processing_status: ProcessingStatus
    processing_error: str | None
    retry_count: int
