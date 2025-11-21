import json
import pydeck as pdk
import requests
import streamlit as st
import numpy as np
import pandas as pd

from utils.database_queries import(
    get_affluence_density, get_alcaldia_boundaries,
    get_average_time_station,
    get_crime_counts_per_station,
    get_hotspot_coords_station,
    get_most_common_robo_station, get_top_3_delitos_station,
    get_top_affluence_stations,
    get_top_crime_stations,
    get_top_robo_stations,
    get_total_crimes_station,
    get_total_robos_station
)

# Plot crimes Pydeck map
@st.cache_data
def plot_crime_map(highlight_station=None, show_affluence=False):
    df_stations = get_crime_counts_per_station()
    df_bounds = get_alcaldia_boundaries()
    df_affluence = get_affluence_density()

    # Borough Limits
    geojson_features = []
    for _, row in df_bounds.iterrows():
        try:
            coords = json.loads(row['coordinates']) if isinstance(row['coordinates'], str) else row['coordinates']
            if isinstance(coords, np.ndarray):
                coords = coords.tolist()

            if row['geom_type'] == 'Polygon':
                rings = coords
            elif row['geom_type'] == 'MultiPolygon':
                rings = [ring for poly in coords for ring in poly]
            else:
                continue

            for ring in rings:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[(lon, lat) for lon, lat in ring]]
                    },
                    "properties": {"nombre": row["nombre"]}
                })
        except Exception as e:
            print(f"Error parsing polygon: {e}")

    geojson_data = {
        "type": "FeatureCollection",
        "features": geojson_features
    }

    # Crimes
    crime_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_stations,
        get_position=["lon", "lat"],
        stroked=True,
        filled=True,
        get_fill_color="[crime_count * 10, 255, 100, 140]",
        get_line_color=[0, 0, 0, 105],
        line_width_min_pixels=3,
        get_radius="crime_count * 0.003",
        radius_scale=80,
        radius_min_pixels=5,
        pickable=True,
        auto_highlight=True
    )

    affluence_layer = pdk.Layer(
        "HeatmapLayer",
        data=df_affluence,
        get_position=["lon", "lat"],
        get_weight="total_afluence",
        radiusPixels=60,
        aggregation="SUM"
    )

    tooltip = {
        "html": """
            <b>Estación:</b> {nombre} <br/>
            <b>Línea:</b> {linea} <br/>
            <b>Número de crímenes:</b> {crime_count} <br/>
        """,
        "style": {
            "backgroundColor": "black",
            "color": "white",
            "fontSize": "12px",
        }
    }

    highlight_layer = None
    if highlight_station is not None:
        highlight_layer = pdk.Layer(
            "ScatterplotLayer",
            data=[highlight_station.to_dict()],
            get_position=["lon", "lat"],
            get_radius=900,
            stroked=True,
            get_color=[250, 250, 250],
            get_line_color=[0, 0, 0, 105],
            line_width_min_pixels=2,
            pickable=False
        )

    # Alcaldía boundary layer
    boundary_layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_data,
        stroked=True,
        get_line_color=[80, 80, 80],
        line_width_min_pixels=3
    )

    view_state = pdk.ViewState(
        latitude=19.3176,
        longitude=-99.1332,
        zoom=9.7,
        pitch=0
    )

    layers = [boundary_layer, crime_layer]
    if highlight_layer:
        layers.append(highlight_layer)
    if show_affluence:
        layers = [boundary_layer, affluence_layer, crime_layer]

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style=pdk.map_styles.DARK,
        tooltip=tooltip
    )

# Stats
def reverse_geocode(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "zoom": 18
    }
    headers = {
        "User-Agent": "CrimesFGJApp/1.0 (paolasollano@gmail.com)"  # ✅ Use your real email or domain
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("display_name", "Dirección no disponible")
    except Exception as e:
        print(f"Error en geocodificación inversa: {e}")
        return "Error al obtener dirección"

@st.cache_data
def show_station_stats(nombre, linea, radius_m=100):
    if not nombre:
        st.info("Selecciona una estación para ver sus estadísticas.")
        return

    st.markdown(f"### Estadísticas para **{nombre}** de la línea **{linea}**")

    total_crimes = get_total_crimes_station(nombre, radius_m)
    total_robos = get_total_robos_station(nombre, radius_m)
    most_common_robo = get_most_common_robo_station(nombre, radius_m)
    top_3_crimes = get_top_3_delitos_station(nombre, radius_m)
    avg_hour, avg_minute = get_average_time_station(nombre, radius_m)
    hotspot = get_hotspot_coords_station(nombre, radius_m)
    address = reverse_geocode(hotspot["latitud"], hotspot["longitud"])

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de crímenes", total_crimes)
        st.metric("Total de robos", total_robos)
        st.markdown(f"**Tipo de robo más común:** {most_common_robo}")
    with col2:
        st.markdown(f"**Hora promedio del crimen:** {int(avg_hour):02d}:{int(avg_minute):02d}")
        st.markdown(f"**Coordenada más frecuente:** {address}")
    
    st.markdown("#### Top 3 delitos más comunes:")
    col3, col4, col5 = st.columns(3)
    
    with col3:
        st.metric(label=top_3_crimes.iloc[0]['delito'], value=top_3_crimes.iloc[0]['count'])
    with col4:
        st.metric(label=top_3_crimes.iloc[1]['delito'], value=top_3_crimes.iloc[1]['count'])
    with col5:
        st.metric(label=top_3_crimes.iloc[2]['delito'], value=top_3_crimes.iloc[2]['count'])

# Data table
@st.cache_data
def view_tables():
    df_crimes = get_top_crime_stations()
    df_crimes = df_crimes.rename(columns={"estacion": "Estación", "crime_count": "Número de crímenes"})

    df_robos = get_top_robo_stations()
    df_robos = df_robos.rename(columns={"estacion": "Estación", "robo_count": "Número de robos"})

    df_affluence = get_top_affluence_stations()
    df_affluence = df_affluence.rename(columns={"estacion": "Estación", "total_afluence": "Afluencia total"})

    df_crimes.index += 1
    df_robos.index += 1
    df_affluence.index += 1

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("<div style='height: 90px'><h3>Estaciones con más crímenes</h3></div>", unsafe_allow_html=True)
        st.dataframe(df_crimes)

    with col2:
        st.markdown("<div style='height: 90px'><h3>Estaciones con más robos</h3></div>", unsafe_allow_html=True)
        st.dataframe(df_robos)

    with col3:
        st.markdown("<div style='height: 90px'><h3>Estaciones con más afluencia</h3></div>", unsafe_allow_html=True)
        st.dataframe(df_affluence)

def get_thermometer_color(probability):
    if probability < 5:
        return [0, 255, 0, 200]
    elif probability < 15:
        return [255, 255, 0, 200]
    elif probability < 25:
        return [255, 140, 0, 200]
    elif probability < 40:
        return [255, 0, 0, 200]
    else:
        return [148, 0, 211, 220]


def plot_prediction_animated_map(station_lat, station_lon, station_name, prediction_row, radius_m):
    try:
        df_bounds = get_alcaldia_boundaries() 
    except NameError:
        df_bounds = pd.DataFrame()

    geojson_features = []
    if not df_bounds.empty:
        for _, row in df_bounds.iterrows():
            try:
                coords = json.loads(row['coordinates']) if isinstance(row['coordinates'], str) else row['coordinates']
                if isinstance(coords, np.ndarray):
                    coords = coords.tolist()
                
                rings = coords if row['geom_type'] == 'Polygon' else [ring for poly in coords for ring in poly]
                for ring in rings:
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [[(lon, lat) for lon, lat in ring]]},
                    })
            except Exception:
                continue

    geojson_data = {"type": "FeatureCollection", "features": geojson_features}

    prob = float(prediction_row['Prob. de evento (%)'])

    MAX_HEIGHT_M = 3500
    VISUAL_CEILING = 60
    
    fill_ratio = prob / VISUAL_CEILING
    liquid_height = fill_ratio * MAX_HEIGHT_M
    
    liquid_height = min(liquid_height, MAX_HEIGHT_M)
    liquid_height = max(200, liquid_height)

    data_point = pd.DataFrame({
        'lat': [float(station_lat)],
        'lon': [float(station_lon)],
        'name': [str(station_name)],
        'prob': [prob],
        'liquid_height': [float(liquid_height)],
        'glass_height': [float(MAX_HEIGHT_M)]
    })
    
    boundary_layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_data,
        stroked=True,
        filled=False,
        get_line_color=[80, 80, 80],
        line_width_min_pixels=2
    )

    context_layer = pdk.Layer(
        "ScatterplotLayer",
        data=data_point,
        get_position=["lon", "lat"],
        get_radius=radius_m,
        stroked=True,
        filled=False,
        get_line_color=[0, 255, 255, 80],
        line_width_min_pixels=2,
    )

    glass_layer = pdk.Layer(
        "ColumnLayer",
        data=data_point,
        get_position=["lon", "lat"],
        get_elevation="glass_height",
        elevation_scale=1,
        radius=250, 
        get_fill_color=[220, 220, 220, 30],
        get_line_color=[255, 255, 255, 150], 
        stroked=True,
        line_width_min_pixels=2,
        pickable=False,
        extruded=True,
    )

    liquid_layer = pdk.Layer(
        "ColumnLayer",
        data=data_point,
        get_position=["lon", "lat"],
        get_elevation="liquid_height",
        elevation_scale=1,
        radius=120,
        get_fill_color=get_thermometer_color(prob),
        pickable=True,
        auto_highlight=True,
        extruded=True, 
        material={
            "ambient": 0.8, 
            "diffuse": 0.9,
            "shininess": 32,
            "specularColor": [255, 255, 255]
        }
    )

    view_state = pdk.ViewState(
        latitude=station_lat,
        longitude=station_lon,
        zoom=11.5,
        pitch=60, 
        bearing=15 
    )

    tooltip = {
        "html": f"<b>Estación:</b> {station_name}<br/><b>Riesgo:</b> {{prob}}%",
        "style": {"backgroundColor": "black", "color": "white"}
    }

    return pdk.Deck(
        layers=[boundary_layer, context_layer, liquid_layer, glass_layer],
        initial_view_state=view_state,
        map_style=pdk.map_styles.DARK,
        tooltip=tooltip
    )