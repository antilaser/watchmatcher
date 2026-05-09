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
    dashboard_auth_enabled: bool = True
    dashboard_auth_username: str = "admin"
    dashboard_auth_password: str = ""
    webhook_hmac_secret: str = "change-me-too"

    database_url: str = "postgresql+asyncpg://watchmatch:watchmatch@localhost:5432/watchmatch"
    database_url_sync: str = "postgresql+psycopg://watchmatch:watchmatch@localhost:5432/watchmatch"

    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 30
    openai_vision_model: str = "gpt-4o-mini"
    openai_vision_timeout_seconds: int = 60
    vision_enabled: bool = True
    vision_max_image_bytes: int = 8_000_000
    media_storage_dir: str = "media"
    listing_image_max_bytes: int = 5_000_000
    listing_image_retention_days: int = 14
    llm_enabled: bool = True
    llm_fallback_enabled: bool = True

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    telegram_enabled: bool = False
    # Used for Telegram webhook requests via X-Telegram-Bot-Api-Secret-Token.
    # Falls back to WEBHOOK_HMAC_SECRET when left empty.
    telegram_webhook_secret: str = ""

    default_workspace_name: str = "default"
    default_min_match_confidence: float = 0.75
    default_min_profit_threshold: float = 300.0
    # Unpriced pairs: alerts/dashboard use this floor (was hardcoded 0.85; ref-only pairs are often ~0.7–0.8).
    unpriced_alert_min_match_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    # When buy/sell share the same reference string, bump score so manual-review queues stay usable.
    exact_reference_match_score_floor: float = Field(default=0.86, ge=0.0, le=1.0)
    # Only pair offers/requests whose source WhatsApp message is at most this old (by original_timestamp).
    match_candidate_max_age_days: int = Field(default=3, ge=1, le=365)
    # Profit display: AUTO = same ISO as both legs when they match, else USD. Set EUR/USD/… to force XE conversion into that currency.
    profit_reporting_currency: str = Field(default="AUTO")
    # Xe Currency Data API (https://xecdapi.xe.com) — Basic auth: account id + api key from https://currencydata.xe.com/
    xe_account_id: str = ""
    xe_api_key: str = ""
    default_shipping_cost: float = 80.0
    default_fee_percent: float = 0.01
    default_fixed_fee: float = 0.0
    default_risk_buffer: float = 100.0

    rule_parse_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    alert_dedupe_hours: int = 24
    expire_offer_days: int = 30
    expire_request_days: int = 60
    listing_retention_days: int = 14
    message_retention_days: int = 14

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
