import streamlit as st
import streamlit.components.v1 as components
from interactive_folium import load_data, clean_data, year_slider, create_map
import os

#-------------------------------
#---------Custom Styling--------
#-------------------------------
st.markdown("""
    <style>
    html, body {
        background-color: #F1EBDE !important;
        color: black !important;
    }
    [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
        background-color: #F1EBDE !important;
    }
    header[data-testid="stHeader"] {
        background-color: #F1EBDE !important;
    }
    .st-emotion-cache-1avcm0n {
        background-color: #F1EBDE !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <h1 style='
        color: black;
        font-size: 3em;
        font-weight: bold;
    '>Robberies near or in metro stations in Mexico City</h1>
""", unsafe_allow_html=True)

st.markdown("""
    <p style='color:black; font-size:1.1em;'>
        This map shows the amount of robberies registered in a single year. To change the year
        selected you can use the slider below.
    </p>
""", unsafe_allow_html=True)

#-------------------------------
#-------- Load & Clean ---------
#-------------------------------
df_raw, _, _ = load_data()
df_clean = clean_data(df_raw)

#-------------------------------
#-------- Year Slider ----------
#-------------------------------
selected_year = year_slider(df_clean)

#-------------------------------
#-------- Map Creation ---------
#-------------------------------
create_map(selected_year)

st.markdown(f"""
    <h3 style='color:black;'>Year selected: {selected_year}</h3>
""", unsafe_allow_html=True)

# Embed saved map
map_path = "output/robos_near_metro.html"
if os.path.exists(map_path):
    with open(map_path, "r", encoding="utf-8") as f:
        map_html = f.read()
    components.html(map_html, height=600, scrolling=True)
else:
    st.error("No map found. Please check if the map was generated correctly.")