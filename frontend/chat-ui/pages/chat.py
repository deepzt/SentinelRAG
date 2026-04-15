import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import api

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SentinelRAG — Chat",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("token") or not st.session_state.get("user"):
    st.switch_page("pages/login.py")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .role-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-top: 4px;
    }
    .role-engineer { background:#dbeafe; color:#1d4ed8; }
    .role-hr        { background:#fce7f3; color:#9d174d; }
    .role-manager   { background:#dcfce7; color:#166534; }
    .role-admin     { background:#fef3c7; color:#92400e; }
    .citation-box {
        background: #f8fafc;
        border-left: 3px solid #6366f1;
        border-radius: 0 6px 6px 0;
        padding: 8px 12px;
        margin-top: 8px;
        font-size: 0.85rem;
    }
    .citation-title { font-weight: 600; color: #1e293b; }
    .citation-meta  { color: #64748b; }
    .denied-banner {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 6px;
        padding: 10px 14px;
        color: #9a3412;
        font-size: 0.9rem;
        margin-top: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session helpers ───────────────────────────────────────────────────────────
token: str = st.session_state["token"]
user: dict = st.session_state["user"]

if "messages" not in st.session_state:
    st.session_state["messages"] = []


def _handle_expired() -> None:
    st.session_state.clear()
    st.session_state["session_expired"] = True
    st.switch_page("pages/login.py")


def _role_badge(role: str) -> str:
    css = {
        "engineer": "role-engineer",
        "hr": "role-hr",
        "manager": "role-manager",
        "admin": "role-admin",
    }.get(role, "role-engineer")
    return f'<span class="role-badge {css}">{role.upper()}</span>'


def _render_citations(citations: list[dict]) -> None:
    if not citations:
        return
    lines = []
    for i, c in enumerate(citations, 1):
        dept = c.get("department", "")
        dtype = c.get("doc_type", "")
        score = c.get("score", 0)
        title = c.get("title", "Unknown")
        section = c.get("section_header", "")
        lines.append(
            f'<div class="citation-box">'
            f'<span class="citation-title">[{i}] {title}</span><br>'
            f'<span class="citation-meta">Section: {section} &nbsp;·&nbsp; '
            f'{dept} / {dtype} &nbsp;·&nbsp; relevance: {score:.0%}</span>'
            f"</div>"
        )
    st.markdown("\n".join(lines), unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ SentinelRAG")
    st.divider()

    st.markdown(f"**{user.get('username', 'Unknown')}**")
    st.markdown(
        _role_badge(user.get("role", "")), unsafe_allow_html=True
    )
    st.caption(f"Department: {user.get('department', '—')}")
    st.caption(f"Email: {user.get('email', '—')}")

    st.divider()

    if user.get("role") in ("manager", "admin"):
        if st.button("Analytics Dashboard", use_container_width=True):
            st.switch_page("pages/admin.py")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

    st.divider()

    if st.button("Sign Out", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.switch_page("pages/login.py")

# ── Main header ───────────────────────────────────────────────────────────────
st.markdown("## 💬 Chat")
st.caption(
    f"You are signed in as **{user.get('username')}** ({user.get('role')}). "
    "You will only see documents your role is permitted to access."
)

# ── Message history ───────────────────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            if msg.get("access_decision") == "denied" and not msg.get("citations"):
                st.markdown(
                    '<div class="denied-banner">'
                    "⚠️ No accessible documents found for your query. "
                    "This topic may not be in your role's knowledge base."
                    "</div>",
                    unsafe_allow_html=True,
                )
            elif msg.get("citations"):
                _render_citations(msg["citations"])

# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input(
    "Ask anything about company knowledge…",
    max_chars=2000,
)

if prompt:
    # Render user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # Call backend
    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base…"):
            result, err = api.send_query(token, prompt)

        if err:
            if api.is_session_expired_error(err):
                _handle_expired()
            else:
                st.error(f"Error: {err}")
                st.session_state["messages"].append(
                    {"role": "assistant", "content": f"⚠️ {err}", "citations": []}
                )
        else:
            answer = result.get("answer", "No response received.")
            citations = result.get("citations", [])
            access_decision = result.get("access_decision", "allowed")

            st.markdown(answer)

            if access_decision == "denied" and not citations:
                st.markdown(
                    '<div class="denied-banner">'
                    "⚠️ No accessible documents found for your query. "
                    "This topic may not be in your role's knowledge base."
                    "</div>",
                    unsafe_allow_html=True,
                )
            elif citations:
                _render_citations(citations)

            st.session_state["messages"].append(
                {
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                    "access_decision": access_decision,
                }
            )
