import streamlit as st

# Entry point — Streamlit runs this first when the user hits the root URL.
# Each page handles its own set_page_config and auth guard.
# This file only routes the initial landing to the correct page.

st.set_page_config(
    page_title="SentinelRAG",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if st.session_state.get("token") and st.session_state.get("user"):
    st.switch_page("pages/chat.py")
else:
    st.switch_page("pages/login.py")
