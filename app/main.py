"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.routes import (
    alerts,
    groups,
    health,
    ingest,
    matches,
    messages,
    offers,
    requests,
    review,
    sources,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.app_log_level)
    log = get_logger(__name__)
    log.info("startup", env=settings.app_env, version=__version__)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="watchmatch",
        version=__version__,
        lifespan=lifespan,
        debug=settings.app_debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    prefix = settings.api_prefix
    app.include_router(sources.router, prefix=prefix)
    app.include_router(groups.router, prefix=prefix)
    app.include_router(messages.router, prefix=prefix)
    app.include_router(offers.router, prefix=prefix)
    app.include_router(requests.router, prefix=prefix)
    app.include_router(matches.router, prefix=prefix)
    app.include_router(alerts.router, prefix=prefix)
    app.include_router(review.router, prefix=prefix)
    app.include_router(ingest.router, prefix=prefix)

    return app


app = create_app()
