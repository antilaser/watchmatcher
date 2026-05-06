"""Schemas for parser/extractor output. The LLM must conform to ExtractedWatchTrade."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import MessageClassification, ParseMethod
from app.parsing.rules import split_calendar_year_reference


class ExtractedWatchTrade(BaseModel):
    """Strict output schema enforced for both rule-based and LLM extraction."""

    model_config = ConfigDict(extra="ignore")

    classification: MessageClassification
    brand: str | None = None
    model_family: str | None = None
    reference: str | None = None
    nickname: str | None = None
    condition: str | None = None
    full_set: bool | None = None
    year: int | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    negotiable: bool | None = None
    location: str | None = None
    notes: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def default_missing_confidence(cls, value):
        return 0.0 if value is None else value

    @model_validator(mode="after")
    def separate_calendar_year_from_reference(self) -> "ExtractedWatchTrade":
        self.reference, self.year = split_calendar_year_reference(self.reference, self.year)
        return self


class ClassificationResult(BaseModel):
    classification: MessageClassification
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None


class ParseResult(BaseModel):
    classification: ClassificationResult
    extracted: ExtractedWatchTrade
    parse_method: ParseMethod
    parse_confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False
    notes: list[str] = Field(default_factory=list)
