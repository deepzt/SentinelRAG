"""Backend API client.

All communication with the FastAPI backend goes through this module.
Never import httpx directly in page files.

Error handling contract:
  - All functions return (data, error_message).
  - On success: (data_dict, None)
  - On failure: (None, human-readable error string)
  - 401 → error starts with "SESSION_EXPIRED:" so callers can redirect to login.
"""

import os
from typing import Any

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
_TIMEOUT = 30.0

_SESSION_EXPIRED = "SESSION_EXPIRED"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _handle_error(r: httpx.Response) -> str:
    if r.status_code == 401:
        return f"{_SESSION_EXPIRED}: Your session has expired. Please log in again."
    if r.status_code == 403:
        return "Access denied."
    try:
        detail = r.json().get("detail", r.text)
    except Exception:
        detail = r.text or f"HTTP {r.status_code}"
    return str(detail)


# ── Auth ──────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> tuple[dict | None, str | None]:
    """POST /auth/login — returns (token_response, error)."""
    try:
        r = httpx.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json(), None
        if r.status_code == 401:
            return None, "Invalid username or password."
        return None, _handle_error(r)
    except httpx.ConnectError:
        return None, "Cannot connect to backend. Is the server running?"
    except httpx.TimeoutException:
        return None, "Request timed out. Please try again."


def get_me(token: str) -> tuple[dict | None, str | None]:
    """GET /auth/me — returns (user_profile, error)."""
    try:
        r = httpx.get(
            f"{BACKEND_URL}/auth/me",
            headers=_headers(token),
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json(), None
        return None, _handle_error(r)
    except httpx.ConnectError:
        return None, "Cannot connect to backend."
    except httpx.TimeoutException:
        return None, "Request timed out."


# ── Query ─────────────────────────────────────────────────────────────────────

def send_query(
    token: str, query: str, top_k: int = 4
) -> tuple[dict | None, str | None]:
    """POST /query — returns (query_response, error)."""
    try:
        r = httpx.post(
            f"{BACKEND_URL}/query",
            json={"query": query, "top_k": top_k},
            headers=_headers(token),
            timeout=60.0,  # LLM can be slow
        )
        if r.status_code == 200:
            return r.json(), None
        return None, _handle_error(r)
    except httpx.ConnectError:
        return None, "Cannot connect to backend."
    except httpx.TimeoutException:
        return None, "Query timed out. The LLM may be processing — try again."


# ── Admin ─────────────────────────────────────────────────────────────────────

def get_audit_report(
    token: str,
    page: int = 1,
    page_size: int = 200,
    decision_filter: str | None = None,
) -> tuple[dict | None, str | None]:
    """GET /admin/audit-report — returns (report, error)."""
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if decision_filter:
        params["decision_filter"] = decision_filter
    try:
        r = httpx.get(
            f"{BACKEND_URL}/admin/audit-report",
            params=params,
            headers=_headers(token),
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json(), None
        return None, _handle_error(r)
    except httpx.ConnectError:
        return None, "Cannot connect to backend."
    except httpx.TimeoutException:
        return None, "Request timed out."


# ── Session helpers ───────────────────────────────────────────────────────────

def is_session_expired_error(error: str) -> bool:
    return error.startswith(_SESSION_EXPIRED)
