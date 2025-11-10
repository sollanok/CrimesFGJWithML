import streamlit as st
from app.theme import theme_css
from utils.map_visualization import plot_crime_density_map, get_station_stats
from utils.database_queries import get_metro_stations

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
