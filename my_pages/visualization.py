import streamlit as st
from app.theme import theme_css
from utils.database_queries import get_metro_stations
from utils.map_visualization import (
    plot_crime_density_map,
    geocode_address,
    get_crimes_near_point,
    summarize_crimes,
    get_station_stats,
)
import pandas as pd

# Make side margins larger
st.set_page_config(layout="wide")

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

# Page content
st.title("Visualización")

st.subheader("Robos históricos cerca de estaciones del metro (2015-2024)")
col1, col2 = st.columns([1, 2])

# Station names
df_stations = get_metro_stations()
station_names = sorted(df_stations['nombre'].astype(str).unique())

with col1:
    selected_station = st.selectbox(
        "Busca una estación para saber sus estadísticas",
        options=station_names,
        index=None,
        placeholder="Ej. Chabacano"
    )

    if selected_station:
        station, stats = get_station_stats(selected_station)
        if station is None:
            st.error("No se encontró la estación.")
        else:
            st.success(f"{station['nombre']} es de la línea: {station['linea']}")
            st.metric("Total de crímenes", stats["total_crimes"])
            st.metric("Total de robos", stats["robos"])
            st.write(f"Tipo de robo más común: **{stats['most_common_robo']}**")
            # Hour formatting
            avg_hour_int = int(stats['avg_hour'])
            suffix = "am" if avg_hour_int < 12 else "pm"
            display_hour = avg_hour_int % 12
            if display_hour == 0:
                display_hour = 12
            
            hour_stat = f"{display_hour}:00 {suffix}"
            
            st.write(f"Hora promedio de los crímenes: **{hour_stat}**")

with col2:
    m = plot_crime_density_map(highlight_station=station if selected_station else None)
    st.components.v1.html(m._repr_html_(), height=600)

st.divider()
st.subheader("Comparación entre dirección y estación (2015-2024)")

col3, col4 = st.columns([1, 1])

with col3:
    address_query = st.text_input("Escribe una dirección o lugar", placeholder="Ej. Av. Universidad 3000, CDMX")

with col4:
    comparison_station = st.selectbox(
        "Selecciona una estación para comparar",
        options=station_names,
        index=None,
        placeholder="Ej. Chabacano"
    )

if address_query and comparison_station:
    location = geocode_address(address_query)
    if location is None:
        st.error("No se pudo geolocalizar la dirección.")
    else:
        crimes_near_address = get_crimes_near_point(location['lat'], location['lon'], radius_m=100)
        address_stats = summarize_crimes(crimes_near_address)

        station, station_stats = get_station_stats(comparison_station)

        st.markdown("### Comparación de estadísticas")
        comparison_data = {
            "Total de crímenes": [station_stats["total_crimes"], address_stats["total_crimes"]],
            "Total de robos": [station_stats["robos"], address_stats["robos"]],
            "Tipo de robo más común": [station_stats["most_common_robo"], address_stats["most_common_robo"]],
            "Hora promedio": [
                f"{station_stats['avg_hour'] % 12 or 12}:00 {'am' if station_stats['avg_hour'] < 12 else 'pm'}",
                f"{address_stats['avg_hour'] % 12 or 12}:00 {'am' if address_stats['avg_hour'] < 12 else 'pm'}"
            ]
        }
        st.table(pd.DataFrame(comparison_data, index=["Estación", "Dirección"]))
