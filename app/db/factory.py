"""Builds the Intake repository from the lifespan's session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repository import IntakeRepository

__all__ = [
    "IntakeRepository",
    "build_repository",
]


def build_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> IntakeRepository:
    """Return the repository over this session factory."""
    return IntakeRepository(session_factory)
