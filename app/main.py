"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import __version__
from app.api.v1.routes import (
    alerts,
    groups,
    health,
    ingest,
    listings,
    matches,
    messages,
    offers,
    requests,
    review,
    sources,
    workspace,
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
    app.include_router(workspace.router, prefix=prefix)
    app.include_router(listings.router, prefix=prefix)

    ui_dir = Path(__file__).resolve().parent / "ui"
    ui_index = ui_dir / "index.html"
    ui_listings = ui_dir / "listings.html"

    @app.get("/dashboard")
    async def dashboard_page() -> FileResponse:
        if not ui_index.is_file():
            raise HTTPException(status_code=404, detail="dashboard UI not found")
        return FileResponse(ui_index, media_type="text/html; charset=utf-8")

    @app.get("/listings")
    async def listings_page() -> FileResponse:
        if not ui_listings.is_file():
            raise HTTPException(status_code=404, detail="listings UI not found")
        return FileResponse(ui_listings, media_type="text/html; charset=utf-8")

    return app


app = create_app()
