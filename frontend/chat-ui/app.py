import streamlit as st

# UI Tester owns this file.
# Pages are defined in pages/ — Streamlit multi-page routing handles navigation.

st.set_page_config(
    page_title="SentinelRAG",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Redirect unauthenticated users to login
if "token" not in st.session_state:
    st.switch_page("pages/login.py")
else:
    st.switch_page("pages/chat.py")
