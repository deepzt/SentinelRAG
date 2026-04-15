"""JWT security and token attack tests.

Covers:
- Expired JWT → 401
- alg:none token → 401 (algorithm confusion attack)
- JWT signed with wrong secret → 401
- JWT with forged role claim → 401 (wrong signature)
- Token for deleted user → 401 (DB re-validation)
- SQL injection attempt in query body → no effect (parameterized SQL)
"""

import base64
import json
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.schemas import UserInToken
from app.core.config import settings
from app.models.user import User
from tests.conftest import get_token


def _make_expired_token(user: User) -> str:
    """Create a syntactically valid JWT that is already expired."""
    claims = UserInToken(
        sub=user.username,
        user_id=str(user.id),
        role=user.role,
        department=user.department,
    )
    payload = {
        **claims.model_dump(),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=61),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _make_alg_none_token(user: User) -> str:
    """Craft a token with alg:none — the algorithm confusion attack.

    Structure: base64url(header).base64url(payload). (empty signature)
    """
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload_data = {
        "sub": user.username,
        "user_id": str(user.id),
        "role": "admin",  # escalated role — must be rejected
        "department": user.department,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    payload = base64.urlsafe_b64encode(
        json.dumps(payload_data).encode()
    ).rstrip(b"=").decode()

    return f"{header}.{payload}."  # empty signature


def _make_wrong_secret_token(user: User) -> str:
    """Sign a valid-looking JWT with a different secret key."""
    claims = UserInToken(
        sub=user.username,
        user_id=str(user.id),
        role=user.role,
        department=user.department,
    )
    payload = {
        **claims.model_dump(),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "completely_wrong_secret_key", algorithm="HS256")


def _make_forged_role_token(user: User) -> str:
    """Sign a token where the role is escalated to 'admin', using a wrong key.

    A real attacker can't sign with the real key, so any role escalation
    in the payload will produce an invalid signature.
    """
    payload = {
        "sub": user.username,
        "user_id": str(user.id),
        "role": "admin",  # forged escalation
        "department": user.department,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, "attacker_does_not_know_real_secret", algorithm="HS256")


# ── Expired token ─────────────────────────────────────────────────────────────

async def test_expired_token_rejected(client: AsyncClient, engineer_user: User):
    token = _make_expired_token(engineer_user)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    # Generic message only — no token internals
    assert "expired" not in response.text.lower() or response.json().get("detail") in (
        "Invalid or expired token",
        "Could not validate credentials",
    )


# ── alg:none attack ───────────────────────────────────────────────────────────

async def test_alg_none_token_rejected(client: AsyncClient, engineer_user: User):
    """alg:none (unsigned) tokens must be rejected with 401, not accepted."""
    token = _make_alg_none_token(engineer_user)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_alg_none_cannot_escalate_to_admin(client: AsyncClient, engineer_user: User):
    """Even if alg:none token claims role=admin, it must be rejected."""
    token = _make_alg_none_token(engineer_user)
    response = await client.get(
        "/admin/audit-report", headers={"Authorization": f"Bearer {token}"}
    )
    # Must be 401 (bad token) not 200 (accepted with escalated role)
    assert response.status_code in (401, 403)
    assert response.status_code != 200


# ── Wrong secret ──────────────────────────────────────────────────────────────

async def test_wrong_secret_token_rejected(client: AsyncClient, engineer_user: User):
    token = _make_wrong_secret_token(engineer_user)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ── Forged role ───────────────────────────────────────────────────────────────

async def test_forged_admin_role_rejected(client: AsyncClient, engineer_user: User):
    """An attacker who forges role=admin in the JWT payload cannot bypass RBAC.

    The token is signed with the wrong key → signature check fails → 401.
    """
    token = _make_forged_role_token(engineer_user)
    response = await client.get(
        "/admin/audit-report", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# ── Deleted user ──────────────────────────────────────────────────────────────

async def test_token_for_deleted_user_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    """A valid JWT for a user who was deleted from the DB must be rejected.

    This tests that get_current_user re-validates the 'sub' claim against the DB
    on every request, not just on login.
    """
    import uuid
    from app.auth.password import hash_password
    from app.models.user import User

    # Create a temporary user
    temp_user = User(
        id=uuid.uuid4(),
        username=f"temp_{uuid.uuid4().hex[:8]}",
        email="temp@sentinelrag.local",
        hashed_password=hash_password("temp_pass"),
        role="engineer",
        department="platform",
    )
    db_session.add(temp_user)
    await db_session.commit()

    # Issue a real, valid token for this user
    claims = UserInToken(
        sub=temp_user.username,
        user_id=str(temp_user.id),
        role=temp_user.role,
        department=temp_user.department,
    )
    token = create_access_token(claims)

    # Verify token works before deletion
    pre_delete = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert pre_delete.status_code == 200

    # Delete the user
    await db_session.delete(temp_user)
    await db_session.commit()

    # Token is still syntactically valid but user no longer exists → must be 401
    post_delete = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert post_delete.status_code == 401


# ── SQL injection probe ───────────────────────────────────────────────────────

async def test_sql_injection_in_query_has_no_effect(
    client: AsyncClient, engineer_user: User, engineer_policy
):
    """SQL injection in the query body must have no effect on retrieval.

    The query string goes through the embedding model first; the resulting vector
    is passed to PostgreSQL as a parameterized bind. Raw SQL in the query body
    cannot influence the WHERE clause.
    """
    token = await get_token(client, engineer_user)
    injection_payloads = [
        "' OR role_required='hr'--",
        "'; DROP TABLE document_chunks;--",
        "1=1 UNION SELECT * FROM users--",
    ]
    for payload in injection_payloads:
        response = await client.post(
            "/query",
            json={"query": payload},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Must return 200 (processed normally) or 422 (validation),
        # never 500 (which could indicate injection caused an error)
        assert response.status_code in (200, 422), (
            f"Unexpected status {response.status_code} for payload: {payload!r}"
        )
        if response.status_code == 200:
            data = response.json()
            # No cross-role data may appear
            assert "hr" not in str(data.get("citations", [])).lower()
