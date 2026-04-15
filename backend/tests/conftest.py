"""Pytest fixtures for SentinelRAG backend tests.

All tests run against a real PostgreSQL database (same dialect as production).
SQLite is intentionally avoided — pgvector and JSONB operators are Postgres-only.

DATABASE_URL is pulled from the environment (set in .env or Docker Compose).

Isolation strategy:
  - Each test gets its own AsyncSession.
  - User fixtures commit their inserts (because write_audit_log calls db.commit()
    internally, so we can't rely on pure transaction rollback for isolation).
  - User fixtures delete their own rows on teardown via a yield fixture.
  - Audit log rows accumulate across tests (append-only by design).
  - Tables are NOT dropped at the end — the Alembic-migrated schema is preserved.
"""

import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.password import hash_password
from app.core.database import get_db
from app.models.access_policy import AccessPolicy
from app.models.user import User

# ── Engine ───────────────────────────────────────────────────────────────────

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Per-test database session. SQLAlchemy 2.0 compatible."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


# ── Test users ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def engineer_user(db_session: AsyncSession) -> User:
    """Create a unique engineer user; delete it after the test."""
    user = User(
        id=uuid.uuid4(),
        username=f"test_eng_{uuid.uuid4().hex[:8]}",
        email="alice_test@sentinelrag.local",
        hashed_password=hash_password("test_password"),
        role="engineer",
        department="platform",
    )
    db_session.add(user)
    await db_session.commit()
    yield user
    await db_session.delete(user)
    await db_session.commit()


@pytest_asyncio.fixture
async def hr_user(db_session: AsyncSession) -> User:
    """Create a unique HR user; delete it after the test."""
    user = User(
        id=uuid.uuid4(),
        username=f"test_hr_{uuid.uuid4().hex[:8]}",
        email="bob_test@sentinelrag.local",
        hashed_password=hash_password("test_password"),
        role="hr",
        department="people_ops",
    )
    db_session.add(user)
    await db_session.commit()
    yield user
    await db_session.delete(user)
    await db_session.commit()


@pytest_asyncio.fixture
async def manager_user(db_session: AsyncSession) -> User:
    """Create a unique manager user; delete it after the test."""
    user = User(
        id=uuid.uuid4(),
        username=f"test_mgr_{uuid.uuid4().hex[:8]}",
        email="charlie_test@sentinelrag.local",
        hashed_password=hash_password("test_password"),
        role="manager",
        department="engineering",
    )
    db_session.add(user)
    await db_session.commit()
    yield user
    await db_session.delete(user)
    await db_session.commit()


# ── Access policies ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def engineer_policy(db_session: AsyncSession) -> AccessPolicy:
    """Insert an engineer access policy; delete it after the test.

    Uses a unique role name to avoid conflicts with the seeded policy.
    """
    policy = AccessPolicy(
        role="engineer",
        department="engineering",
        allowed_classification="internal",
    )
    db_session.add(policy)
    try:
        await db_session.commit()
    except Exception:
        # Policy already exists from seed — that's fine, use what's there
        await db_session.rollback()
    yield policy


@pytest_asyncio.fixture
async def manager_policies(db_session: AsyncSession) -> list[AccessPolicy]:
    """Ensure manager policies exist (engineering + hr + legal)."""
    # These should already exist from seed_db — just check and yield
    from sqlalchemy import select

    result = await db_session.execute(
        select(AccessPolicy).where(AccessPolicy.role == "manager")
    )
    policies = result.scalars().all()
    yield policies


# ── FastAPI test client ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """AsyncClient backed by the real FastAPI app with DB session injected."""
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth helpers ─────────────────────────────────────────────────────────────

async def get_token(client: AsyncClient, user: User, password: str = "test_password") -> str:
    """Log in as the given user and return the access token."""
    response = await client.post(
        "/auth/login",
        json={"username": user.username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]
