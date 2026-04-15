"""Pytest fixtures for SentinelRAG backend tests.

All tests use a real PostgreSQL database (same dialect as production).
SQLite is intentionally avoided — pgvector and JSONB operators are Postgres-only.

The DATABASE_URL is pulled from the environment (set in .env or CI).
Each test function gets a fresh transaction that is rolled back on teardown,
keeping tests isolated without truncating tables.
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.password import hash_password
from app.core.database import Base, get_db
from app.models.access_policy import AccessPolicy
from app.models.user import User

# ── Engine ──────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per session; drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Per-test DB session wrapped in a savepoint that rolls back."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── Test users + policies ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def engineer_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"alice_test_{uuid.uuid4().hex[:6]}",
        email="alice@test.local",
        hashed_password=hash_password("test_password"),
        role="engineer",
        department="platform",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def hr_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"bob_test_{uuid.uuid4().hex[:6]}",
        email="bob@test.local",
        hashed_password=hash_password("test_password"),
        role="hr",
        department="people_ops",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def engineer_policy(db_session: AsyncSession) -> AccessPolicy:
    policy = AccessPolicy(
        role="engineer",
        department="engineering",
        allowed_classification="internal",
    )
    db_session.add(policy)
    await db_session.flush()
    return policy


# ── FastAPI test client ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """AsyncClient with DB session override."""
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
