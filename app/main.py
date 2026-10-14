"""App factory and lifespan.

Lifespan creates the async engine, the shared httpx client and the Slack client
once and closes them at shutdown. Run with
``uvicorn --factory app.main:create_app`` (settings are read from the
environment only when the server starts, never on import).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, intakes, slack
from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.slack.factory import build_slack_client


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app.

    Args:
        settings: Configuration; read from the environment and ``.env`` if omitted.
    """
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        app.state.settings = settings
        app.state.session_factory = create_session_factory(engine)
        app.state.http_client = httpx.AsyncClient()
        app.state.slack_client = build_slack_client(settings)
        try:
            yield
        finally:
            await app.state.http_client.aclose()
            await engine.dispose()

    app = FastAPI(title="Hermes Intake API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    app.include_router(health.router)
    app.include_router(intakes.router)
    app.include_router(slack.router)
    return app
