"""Admin endpoint tests.

Covers:
- GET /admin/audit-report  manager role → 200 with paginated results
- GET /admin/audit-report  engineer role → 403
- GET /admin/audit-report  hr role → 403
- GET /admin/audit-report  unauthenticated → 403
- GET /admin/audit-report  pagination parameters validated (page_size bounded)
- Audit report contains correct counts after test queries
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import get_token


async def test_manager_can_access_audit_report(
    client: AsyncClient, manager_user: User, manager_policies
):
    token = await get_token(client, manager_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # Response shape must match AuditReportResponse
    assert "items" in data
    assert "total" in data
    assert "allowed_count" in data
    assert "denied_count" in data
    assert "page" in data
    assert "page_size" in data


async def test_engineer_blocked_from_audit_report(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    token = await get_token(client, engineer_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


async def test_hr_blocked_from_audit_report(client: AsyncClient, hr_user: User):
    token = await get_token(client, hr_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_audit_report_unauthenticated(client: AsyncClient):
    response = await client.get("/admin/audit-report")
    assert response.status_code == 403


async def test_audit_report_page_size_bounded(
    client: AsyncClient, manager_user: User, manager_policies
):
    """page_size above the max (200) must be rejected with 422."""
    token = await get_token(client, manager_user)
    response = await client.get(
        "/admin/audit-report?page_size=201",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_audit_report_invalid_page_rejected(
    client: AsyncClient, manager_user: User, manager_policies
):
    """page=0 must be rejected (ge=1)."""
    token = await get_token(client, manager_user)
    response = await client.get(
        "/admin/audit-report?page=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_audit_report_counts_after_denied_query(
    client: AsyncClient,
    manager_user: User,
    hr_user: User,
    manager_policies,
    db_session: AsyncSession,
):
    """After a denied query by hr_user, the manager's audit report must show it.

    This is an integration test: query → audit log written → visible in report.
    """
    # hr_user has no policies → query will be denied and logged
    hr_token = await get_token(client, hr_user)
    await client.post(
        "/query",
        json={"query": "test audit visibility query"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )

    # Manager reads the audit report
    mgr_token = await get_token(client, manager_user)
    response = await client.get(
        "/admin/audit-report",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # denied_count must be at least 1 (from the query above)
    assert data["denied_count"] >= 1

    # The denied entry must appear in items
    denied_items = [i for i in data["items"] if i["access_decision"] == "denied"]
    assert len(denied_items) >= 1


async def test_audit_report_decision_filter(
    client: AsyncClient, manager_user: User, manager_policies
):
    """decision_filter=denied must only return denied rows."""
    token = await get_token(client, manager_user)
    response = await client.get(
        "/admin/audit-report?decision_filter=denied",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["access_decision"] == "denied"
