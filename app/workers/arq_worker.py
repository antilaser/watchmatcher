"""arq WorkerSettings entrypoint. Run with: `arq app.workers.arq_worker.WorkerSettings`."""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.workers.tasks import (
    cleanup_expired_entities_job,
    process_raw_message_job,
    recompute_open_requests_job,
)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [
        process_raw_message_job,
        recompute_open_requests_job,
        cleanup_expired_entities_job,
    ]
    cron_jobs = [
        cron(recompute_open_requests_job, minute={0, 15, 30, 45}),
        cron(cleanup_expired_entities_job, hour=3, minute=0),
    ]
    max_jobs = 20
