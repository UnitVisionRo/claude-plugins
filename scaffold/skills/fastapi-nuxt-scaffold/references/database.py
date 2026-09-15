from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from environment import settings

DATABASE_URL: URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    # QueuePool isn't compatible with the asyncio engine; this is its async equivalent.
    poolclass=AsyncAdaptedQueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    autoflush=False,
    # Keep attributes readable after commit (no refresh round-trip during response mapping).
    expire_on_commit=False,
)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one ``AsyncSession`` per request, shared across services.

    The request is attached to ``session.info`` so helpers (e.g. current-user lookup)
    can reach it regardless of dependency-resolution order. Commits are explicit in
    services; the session is closed on exit. Pass this session into service functions
    rather than opening new ones, so the identity map dedupes within the request
    (see api/CLAUDE.md — async rules).
    """
    async with async_session_factory() as session:
        session.info["_request"] = request
        yield session


def make_session() -> AsyncSession:
    """Create a standalone ``AsyncSession`` for use outside a request (jobs/scripts)."""
    return async_session_factory()
