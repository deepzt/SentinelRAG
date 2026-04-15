"""Auth endpoint tests.

Covers:
- POST /auth/login  happy path → returns JWT
- POST /auth/login  wrong password → 401
- POST /auth/login  unknown user → 401
- GET  /auth/me     valid token → returns user profile
- GET  /auth/me     no token → 403
- GET  /auth/me     tampered token → 401
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, engineer_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": engineer_user.username, "password": "test_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, engineer_user: User):
    response = await client.post(
        "/auth/login",
        json={"username": engineer_user.username, "password": "wrong_password"},
    )
    assert response.status_code == 401
    # Generic message — no username enumeration
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={"username": "nobody", "password": "irrelevant"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_me_returns_profile(client: AsyncClient, engineer_user: User):
    # Login first
    login = await client.post(
        "/auth/login",
        json={"username": engineer_user.username, "password": "test_password"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == engineer_user.username
    assert data["role"] == "engineer"
    # Sensitive fields must not be present
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_rejects_tampered_token(client: AsyncClient):
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer this.is.not.a.valid.jwt"}
    )
    assert response.status_code == 401
