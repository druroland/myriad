"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from myriad.core.database import Base
from myriad.main import create_app

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session.

    Each test gets a fresh session that is rolled back after the test.
    """
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        # Rollback any changes made during the test
        await session.rollback()


@pytest.fixture
async def db_with_commit(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session that commits changes.

    Use this when you need changes to persist across multiple operations
    in a single test (e.g., testing queries after inserts).
    """
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.commit()


@pytest.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Get an async test client for the FastAPI app.

    Note: This requires proper app setup with dependency overrides
    for the database session. For now, this is a placeholder.
    """
    # TODO: Set up proper dependency overrides for the app
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
