"""Auth endpoint tests.

Covers:
- POST /auth/login  happy path for each role → JWT returned
- POST /auth/login  wrong password → 401 (generic message)
- POST /auth/login  unknown username → 401 (same message — no enumeration)
- GET  /auth/me     valid token → user profile without sensitive fields
- GET  /auth/me     no Authorization header → 403
- GET  /auth/me     malformed Bearer token → 401
"""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token


async def test_engineer_login_success(client: AsyncClient, engineer_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": engineer_user.username, "password": "test_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


async def test_hr_login_success(client: AsyncClient, hr_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": hr_user.username, "password": "test_password"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_manager_login_success(client: AsyncClient, manager_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": manager_user.username, "password": "test_password"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client: AsyncClient, engineer_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": engineer_user.username, "password": "wrong_password"},
    )
    assert response.status_code == 401
    # Must use a generic message — no information about why it failed
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_unknown_user_same_error(client: AsyncClient):
    """Unknown username must return the exact same 401 as wrong password (no enumeration)."""
    response = await client.post(
        "/auth/login",
        json={"username": "nobody_exists_here", "password": "irrelevant"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_me_returns_profile(client: AsyncClient, engineer_user: User):
    token = await get_token(client, engineer_user)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == engineer_user.username
    assert data["role"] == "engineer"
    assert data["department"] == "platform"


async def test_me_does_not_leak_password(client: AsyncClient, engineer_user: User):
    token = await get_token(client, engineer_user)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "hashed_password" not in response.json()
    assert "password" not in str(response.json())


async def test_me_requires_auth_header(client: AsyncClient):
    """Missing Authorization header → 403 from HTTPBearer."""
    response = await client.get("/auth/me")
    assert response.status_code == 403


async def test_me_rejects_malformed_token(client: AsyncClient):
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer this.is.not.valid"}
    )
    assert response.status_code == 401


async def test_me_rejects_random_string_as_token(client: AsyncClient):
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer notajwtatall"}
    )
    assert response.status_code == 401
