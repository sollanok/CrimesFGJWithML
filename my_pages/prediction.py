import streamlit as st
from app.theme import theme_css

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

st.title("Predicción")