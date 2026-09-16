"""Destination: api/tests/conftest.py

Fixtures backed by a REAL PostgreSQL database (`TEST_DB_NAME`), not SQLite: the app uses
`timestamptz`, BIGINT identity columns and enum lookup tables with foreign keys, and a SQLite
stand-in would pass tests the production dialect fails.

The schema is built with `create_all` rather than by running migrations. Tests assert on the
behaviour of the current models; whether the migration chain reproduces them is a separate
question, and answering it here would make every test wait for the full history to replay.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from environment import settings
from lib.database import get_session
from main import app
from models.base import Base
from models.enum_tables import seed_enum_tables

TEST_DATABASE_URL: URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.TEST_DB_NAME or f"{settings.DB_NAME}_test",
)


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed_enum_tables(session)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session on the test database, wiped between tests.

    Truncating rather than rolling back a wrapping transaction: the endpoints under test commit
    (the two-factor lockout counter depends on committing before it raises -- see
    `services/auth.py`), so an outer transaction would be an environment the app never runs in.
    """
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as connection:
        await connection.execute(text("TRUNCATE users, user_sessions, user_two_factor RESTART IDENTITY CASCADE"))


@pytest.fixture
async def second_client(client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    """A second browser: the same app and database, its own cookie jar.

    Needed by anything about sessions -- "sign this other device out" is meaningless with one
    cookie jar. It reuses `client`'s transport so the dependency overrides stay in place.
    """
    async with httpx.AsyncClient(transport=client._transport, base_url="http://test") as other:
        yield other


@pytest.fixture
async def client(test_engine: AsyncEngine, db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client bound to the app, sharing the test database and keeping cookies.

    The cookie jar is the point: the auth flow IS cookies, so a client that forgets them would
    test something other than the thing being shipped.
    """
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    # The routers live on the /rest SUB-app, and `dependency_overrides` does not propagate
    # from a parent FastAPI instance into a mounted one -- overriding on `app` alone silently
    # leaves the endpoints talking to the real development database.
    rest_app = app.state.rest_app
    rest_app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    rest_app.dependency_overrides.clear()
    app.dependency_overrides.clear()
