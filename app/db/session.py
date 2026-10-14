"""Engine and session factory creation, called once from the app lifespan."""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    """Create the async engine.

    Args:
        database_url: A ``postgresql+asyncpg://`` URL. With Supabase use the
            direct or session connection on port 5432; the transaction pooler on
            6543 breaks asyncpg prepared statements.
    """
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """Create the session factory handed to the repository."""
    return async_sessionmaker(engine, expire_on_commit=False)
