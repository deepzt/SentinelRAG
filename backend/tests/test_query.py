"""Query endpoint and RBAC tests.

Covers:
- POST /query  no token → 403
- POST /query  role with no access policies → HTTP 200 but access_decision=denied + audit logged
- POST /query  role with policies, no indexed chunks → denied, no doc content leaked
- POST /query  input validation (empty query, too long)
- GET  /documents  RBAC filter — user with no policies gets empty list
- GET  /admin/audit-report  engineer blocked → 403
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.audit_log import AuditLog
from app.models.user import User
from tests.conftest import get_token


async def test_query_requires_auth(client: AsyncClient):
    response = await client.post("/query", json={"query": "What are the AWS rollback steps?"})
    assert response.status_code == 403


async def test_query_denied_when_no_policies(
    client: AsyncClient, hr_user: User, db_session: AsyncSession
):
    """hr_user fixture has no access_policies rows inserted → denied immediately.

    Verifies the early-deny path in rag/service.py (no DB scan performed).
    """
    token = await get_token(client, hr_user)
    response = await client.post(
        "/query",
        json={"query": "What are the employee leave policies?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200  # HTTP 200 — denial is in the payload
    data = response.json()
    assert data["access_decision"] == "denied"
    assert data["chunks_retrieved"] == 0
    assert data["citations"] == []

    # Audit log must be written even for denied requests
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == hr_user.id,
            AuditLog.access_decision == "denied",
        )
    )
    assert result.scalar_one_or_none() is not None, "Denied query must produce an audit log row"


async def test_query_denied_leaks_no_doc_content(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    """Even when access is denied, no internal document content or schema details leak."""
    token = await get_token(client, engineer_user)
    response = await client.post(
        "/query",
        json={"query": "AWS ECS rollback procedure"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = str(response.json())
    # Nothing internal should appear in the response body
    assert "hashed_password" not in body
    assert "access_policies" not in body
    assert "document_chunks" not in body
    assert "traceback" not in body.lower()


async def test_query_input_too_long_rejected(client: AsyncClient, engineer_user: User):
    """Query exceeding max_length=2000 must be rejected with 422."""
    token = await get_token(client, engineer_user)
    response = await client.post(
        "/query",
        json={"query": "x" * 2001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_query_empty_string_rejected(client: AsyncClient, engineer_user: User):
    """Empty query must be rejected (min_length=1) with 422."""
    token = await get_token(client, engineer_user)
    response = await client.post(
        "/query",
        json={"query": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_query_top_k_bounds(client: AsyncClient, engineer_user: User, engineer_policy):
    """top_k must be bounded to [1, 20]; values outside are rejected."""
    token = await get_token(client, engineer_user)

    # top_k=0 → 422
    r = await client.post(
        "/query",
        json={"query": "AWS rollback", "top_k": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422

    # top_k=21 → 422
    r = await client.post(
        "/query",
        json={"query": "AWS rollback", "top_k": 21},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


async def test_documents_no_policies_returns_empty(
    client: AsyncClient, hr_user: User
):
    """User with no access_policies rows sees zero documents."""
    token = await get_token(client, hr_user)
    response = await client.get(
        "/documents", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_admin_endpoint_blocked_for_engineer(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    """Engineer role must receive 403 from /admin/* endpoints."""
    token = await get_token(client, engineer_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


async def test_admin_endpoint_blocked_for_hr(
    client: AsyncClient, hr_user: User
):
    """HR role must also receive 403 from /admin/* endpoints."""
    token = await get_token(client, hr_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
