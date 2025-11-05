import streamlit as st
from app.theme import theme_css

st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

# Page content
st.title("Dashboard")
