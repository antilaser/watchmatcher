"""Application configuration sourced from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "watchmatch"
    app_env: Literal["local", "dev", "staging", "prod", "test"] = "local"
    app_debug: bool = True
    app_log_level: str = "INFO"
    app_timezone: str = "UTC"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    api_cors_origins: str = "*"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    webhook_hmac_secret: str = "change-me-too"

    database_url: str = "postgresql+asyncpg://watchmatch:watchmatch@localhost:5432/watchmatch"
    database_url_sync: str = "postgresql+psycopg://watchmatch:watchmatch@localhost:5432/watchmatch"

    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 30
    llm_enabled: bool = True
    llm_fallback_enabled: bool = True

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    telegram_enabled: bool = False

    default_workspace_name: str = "default"
    default_min_match_confidence: float = 0.75
    default_min_profit_threshold: float = 300.0
    default_shipping_cost: float = 80.0
    default_fee_percent: float = 0.01
    default_fixed_fee: float = 0.0
    default_risk_buffer: float = 100.0

    rule_parse_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    alert_dedupe_hours: int = 24
    expire_offer_days: int = 30
    expire_request_days: int = 60

    @field_validator("api_cors_origins")
    @classmethod
    def _split_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.api_cors_origins or self.api_cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
