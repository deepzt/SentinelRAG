import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import api

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SentinelRAG — Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("token") or not st.session_state.get("user"):
    st.switch_page("pages/login.py")

user: dict = st.session_state["user"]
token: str = st.session_state["token"]

# ── Role guard (UI layer — backend also enforces this) ────────────────────────
if user.get("role") not in ("manager", "admin"):
    st.warning(
        f"⚠️ Analytics dashboard is only available to managers and admins. "
        f"Your role is **{user.get('role')}**."
    )
    st.stop()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .metric-label { font-size: 0.78rem; color: #6b7280; text-transform: uppercase; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ SentinelRAG")
    st.divider()
    st.markdown(f"**{user.get('username')}** — {user.get('role').upper()}")
    st.divider()
    if st.button("Back to Chat", use_container_width=True):
        st.switch_page("pages/chat.py")
    if st.button("Sign Out", use_container_width=True, type="secondary"):
        st.session_state.clear()
        st.switch_page("pages/login.py")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 📊 Analytics Dashboard")
st.caption("Audit log overview — all query activity across all roles.")

# ── Fetch data ────────────────────────────────────────────────────────────────
with st.spinner("Loading audit data…"):
    report, err = api.get_audit_report(token, page_size=200)

if err:
    if api.is_session_expired_error(err):
        st.session_state.clear()
        st.session_state["session_expired"] = True
        st.switch_page("pages/login.py")
    else:
        st.error(f"Failed to load audit data: {err}")
        st.stop()

if not report or report["total"] == 0:
    st.info("No audit data yet. Run some queries first.")
    st.stop()

# ── Metrics row ───────────────────────────────────────────────────────────────
total = report["total"]
allowed = report["allowed_count"]
denied = report["denied_count"]
allow_rate = f"{allowed / total * 100:.1f}%" if total > 0 else "—"
avg_latency = None

items = report["items"]
latencies = [i["response_time_ms"] for i in items if i.get("response_time_ms")]
if latencies:
    avg_latency = f"{sum(latencies) // len(latencies)} ms"

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Queries", total)
col2.metric("Allowed", allowed, delta=None)
col3.metric("Denied", denied, delta=None)
col4.metric("Allow Rate", allow_rate)
col5.metric("Avg Latency", avg_latency or "—")

st.divider()

# ── Query volume chart ────────────────────────────────────────────────────────
try:
    import pandas as pd

    df = pd.DataFrame(items)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("#### Query Volume by Day")
        daily = df.groupby("date").size().reset_index(name="queries")
        daily = daily.sort_values("date")
        st.bar_chart(daily.set_index("date"), color="#6366f1")

    with col_right:
        st.markdown("#### Access Decisions")
        decision_counts = df["access_decision"].value_counts().reset_index()
        decision_counts.columns = ["decision", "count"]
        st.dataframe(
            decision_counts,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ── Recent activity ───────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Recent Denied Queries")
        denied_df = df[df["access_decision"] == "denied"][
            ["created_at", "query", "user_id"]
        ].copy()
        denied_df["created_at"] = denied_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        denied_df["user_id"] = denied_df["user_id"].astype(str).str[:8] + "…"
        denied_df = denied_df.rename(
            columns={"created_at": "Time", "query": "Query", "user_id": "User ID"}
        )
        if denied_df.empty:
            st.success("No denied queries — all roles have appropriate access.")
        else:
            st.dataframe(denied_df.head(20), use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("#### Most Recent Queries")
        recent_df = df[["created_at", "query", "access_decision"]].head(20).copy()
        recent_df["created_at"] = recent_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        recent_df = recent_df.rename(
            columns={
                "created_at": "Time",
                "query": "Query",
                "access_decision": "Decision",
            }
        )
        st.dataframe(recent_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Latency distribution ──────────────────────────────────────────────────
    latency_df = df[df["response_time_ms"].notna()][
        ["created_at", "response_time_ms", "access_decision"]
    ].copy()
    if not latency_df.empty:
        st.markdown("#### Response Latency Over Time (ms)")
        latency_df["created_at"] = latency_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        latency_chart = latency_df.set_index("created_at")[["response_time_ms"]]
        st.line_chart(latency_chart, color="#10b981")

except ImportError:
    # pandas not available — show raw table fallback
    st.warning("Install `pandas` for charts. Showing raw table:")
    st.json(items[:20])
