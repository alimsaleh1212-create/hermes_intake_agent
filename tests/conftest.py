"""Shared test harness: a real Postgres (testcontainers) and an in-process API client.

Seam 1 (the HTTP API) is exercised through ``api_client``. Collaborators the
tests want to control (the agent, the notifier, ...) are swapped through
``app.dependency_overrides`` using the providers in ``app.deps``.
"""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.agents.fake import FakeAgent
from app.core.config import Settings
from app.deps import get_agent, get_notifier
from app.main import create_app
from tests.fakes import RecordingNotifier


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Start one Postgres container per test session on a random host port.

    The schema is created by running the real Alembic migrations, so every API
    test also proves that ``alembic upgrade head`` works.
    """
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        yield url


@pytest.fixture
def settings(database_url: str) -> Settings:
    """Settings for tests: never read the developer's real ``.env``."""
    return Settings(_env_file=None, database_url=database_url)


@pytest.fixture
def fake_agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest.fixture
async def app(
    settings: Settings, fake_agent: FakeAgent, notifier: RecordingNotifier
) -> AsyncIterator[FastAPI]:
    """The FastAPI app with its lifespan running and an empty ``intakes`` table."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE intakes"))
    await engine.dispose()

    application = create_app(settings)
    application.dependency_overrides[get_agent] = lambda: fake_agent
    application.dependency_overrides[get_notifier] = lambda: notifier
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An async HTTP client talking to the app in-process."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
