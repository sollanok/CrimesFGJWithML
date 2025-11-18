import streamlit as st
from assets.css.theme import theme_css
from utils.database_queries import (
    get_metro_stations,
)
from utils.map_visualization import (
    plot_crime_map,
    show_station_stats,
    view_tables
)

# Make side margins larger
st.set_page_config(layout="wide")

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

# Page content
st.title("Visualización de datos históricos")

st.subheader("Datos de las estaciones del metro (2016-2024)")
col1, col2 = st.columns([1, 1])

# Station names
df_stations = get_metro_stations()
station_names = sorted(df_stations['nombre'].astype(str).unique())

with col2:
    st.subheader("Filtrar datos")
    show_affluence = st.checkbox("Agregar afluencia")
    selected_station = st.selectbox(
        "Busca una estación para saber sus estadísticas:",
        options=station_names,
        index=None,
        placeholder="Ej. Chabacano"
    )
    highlight_row = None
    if selected_station:
        highlight_row = df_stations[df_stations["nombre"] == selected_station].iloc[0]
        show_station_stats(selected_station, highlight_row["linea"])

with col1:
    deck_map = plot_crime_map(
        highlight_station=highlight_row,
        show_affluence=show_affluence,
    )
    st.pydeck_chart(deck_map, height=700)

st.divider()

view_tables()