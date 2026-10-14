"""``alembic upgrade head`` (run by the session fixture) creates the spec's table."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base

# The column list from the spec (Implementation Decisions, ``intakes`` table).
SPEC_COLUMNS = {
    "id",
    "client_name",
    "transcript_redacted",
    "transcript_hash",
    "output_json",
    "status",
    "error",
    "model_used",
    "fallback_used",
    "fallback_reason",
    "injection_flagged",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "est_cost_usd",
    "duration_ms",
    "slack_ts",
    "approved_by",
    "decided_at",
    "created_at",
}


async def test_migration_creates_intakes_with_the_spec_columns(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'intakes'"
            )
        )
        columns = {row[0] for row in result}
    await engine.dispose()

    assert columns == SPEC_COLUMNS


async def test_migration_matches_the_sqlalchemy_model(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        diff = await connection.run_sync(
            lambda sync: compare_metadata(
                MigrationContext.configure(sync), Base.metadata
            )
        )
    await engine.dispose()

    assert diff == []
