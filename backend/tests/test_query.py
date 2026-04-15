"""Query endpoint RBAC tests.

Covers:
- POST /query  no token → 403
- POST /query  role with no access policies → denied + audit log written
- POST /query  role with policies but no matching chunks → denied response
- GET  /documents  role isolation — hr user gets no engineering docs

RBAC edge cases handled:
1. Role with zero access_policies rows → denied immediately (no DB scan)
2. Role with policies but zero matching chunks → denied (logged)
3. Audit log written for ALL outcomes including denied requests
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


async def _get_token(client: AsyncClient, user: User, password: str = "test_password") -> str:
    response = await client.post(
        "/auth/login",
        json={"username": user.username, "password": password},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_query_requires_auth(client: AsyncClient):
    response = await client.post("/query", json={"query": "What are the AWS rollback steps?"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_query_denied_when_no_policies(
    client: AsyncClient, hr_user: User, db_session: AsyncSession
):
    """hr_user has no access_policies rows in this test → denied immediately."""
    token = await _get_token(client, hr_user)
    response = await client.post(
        "/query",
        json={"query": "What are the employee leave policies?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200  # HTTP 200, but access_decision = denied
    data = response.json()
    assert data["access_decision"] == "denied"
    assert data["chunks_retrieved"] == 0

    # Audit log must be written even for denied requests
    logs = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == hr_user.id,
            AuditLog.access_decision == "denied",
        )
    )
    assert logs.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_query_denied_returns_no_doc_content(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    """Engineer has policies but no chunks indexed → safe 'no docs found' response."""
    token = await _get_token(client, engineer_user)
    response = await client.post(
        "/query",
        json={"query": "AWS ECS rollback procedure"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # No chunks in DB → denied outcome with empty citations
    assert data["citations"] == []
    assert "hashed_password" not in str(data)
    assert "access_policies" not in str(data)


@pytest.mark.asyncio
async def test_documents_rbac_isolation(
    client: AsyncClient, hr_user: User, engineer_user: User,
    engineer_policy, db_session: AsyncSession
):
    """HR user must not see engineering documents even if they exist."""
    hr_token = await _get_token(client, hr_user)
    response = await client.get(
        "/documents", headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # hr_user has no policies → empty list
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_admin_endpoint_blocked_for_engineer(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    """Non-admin roles must receive 403 from /admin/* endpoints."""
    token = await _get_token(client, engineer_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
