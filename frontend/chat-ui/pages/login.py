import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import api

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="SentinelRAG — Login",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Already authenticated → go straight to chat ───────────────────────────────
if st.session_state.get("token") and st.session_state.get("user"):
    st.switch_page("pages/chat.py")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .login-header { text-align: center; margin-bottom: 8px; }
    .login-subtitle { text-align: center; color: #6b7280; font-size: 0.95rem; margin-bottom: 24px; }
    .demo-label { font-size: 0.82rem; color: #9ca3af; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<h1 class="login-header">🛡️ SentinelRAG</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="login-subtitle">Enterprise RBAC-aware Knowledge Assistant</p>',
    unsafe_allow_html=True,
)

# ── Session-expired banner ────────────────────────────────────────────────────
if st.session_state.pop("session_expired", False):
    st.warning("Your session has expired. Please log in again.")

# ── Login form ────────────────────────────────────────────────────────────────
with st.form("login_form", clear_on_submit=False):
    username = st.text_input("Username", placeholder="e.g. alice")
    password = st.text_input("Password", type="password", placeholder="••••••••")
    submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

if submitted:
    if not username.strip() or not password.strip():
        st.error("Please enter both username and password.")
    else:
        with st.spinner("Signing in…"):
            token_data, err = api.login(username.strip(), password.strip())

        if err:
            st.error(err)
        else:
            # Fetch user profile to populate sidebar
            user_data, err2 = api.get_me(token_data["access_token"])
            if err2:
                st.error(f"Login succeeded but could not load profile: {err2}")
            else:
                token = token_data["access_token"]
                session_data, _ = api.create_chat_session(token)
                st.session_state["token"] = token
                st.session_state["user"] = user_data
                st.session_state["messages"] = []
                st.session_state["session_id"] = session_data["id"] if session_data else None
                st.switch_page("pages/chat.py")

# ── Demo accounts ─────────────────────────────────────────────────────────────
st.divider()
with st.expander("Demo accounts — click to auto-fill", expanded=True):
    st.markdown(
        '<p class="demo-label">These accounts are pre-seeded. '
        "Each role sees a different subset of documents.</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    def _quick_login(uname: str, pwd: str, label: str, col) -> None:
        if col.button(label, use_container_width=True):
            with st.spinner(f"Signing in as {uname}…"):
                token_data, err = api.login(uname, pwd)
            if err:
                st.error(err)
            else:
                token = token_data["access_token"]
                user_data, _ = api.get_me(token)
                session_data, _ = api.create_chat_session(token)
                st.session_state["token"] = token
                st.session_state["user"] = user_data or {"username": uname}
                st.session_state["messages"] = []
                st.session_state["session_id"] = session_data["id"] if session_data else None
                st.switch_page("pages/chat.py")

    _quick_login("alice", "alice123", "Alice — Engineer", col1)
    _quick_login("bob", "bob123", "Bob — HR", col2)
    _quick_login("charlie", "charlie123", "Charlie — Manager", col3)

    st.markdown(
        """
        | User | Role | Can see |
        |------|------|---------|
        | alice | Engineer | AWS runbooks, deployment SOPs |
        | bob | HR | Leave policy, onboarding, reimbursement |
        | charlie | Manager | Engineering + HR + Legal docs |
        """,
        unsafe_allow_html=False,
    )
