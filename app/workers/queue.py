"""Helpers for enqueuing arq jobs from API handlers."""

from __future__ import annotations

from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings

_redis: ArqRedis | None = None


async def get_redis_pool() -> ArqRedis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _redis


async def enqueue_process_raw_message(raw_message_id: UUID) -> None:
    redis = await get_redis_pool()
    await redis.enqueue_job("process_raw_message_job", str(raw_message_id))


async def enqueue_recompute_open_requests() -> None:
    redis = await get_redis_pool()
    await redis.enqueue_job("recompute_open_requests_job")


async def enqueue_cleanup_expired() -> None:
    redis = await get_redis_pool()
    await redis.enqueue_job("cleanup_expired_entities_job")
