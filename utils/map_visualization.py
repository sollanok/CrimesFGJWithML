import streamlit as st
import numpy as np
import pandas as pd
import folium
import json
from sklearn.neighbors import BallTree
from utils.database_queries import (
    get_crimes,
    get_metro_stations,
    get_alcaldia_boundaries
)
from geopy.geocoders import Nominatim
import pydeck as pdk

# Can't do BallTree in query, so use another function here.
@st.cache_data
def get_crime_counts_per_station(radius_m=100):
    df_crimes = get_crimes()
    df_stations = get_metro_stations()

    # Prepare coordinates in radians
    A = np.radians(df_crimes[['latitud', 'longitud']].values)
    B = np.radians(df_stations[['lat', 'lon']].values)

    # Build BallTree and query
    tree = BallTree(B, metric='haversine')
    r = radius_m / 6371000.0  # convert meters to radians
    idxs = tree.query_radius(A, r=r)

    # Map crimes to stations
    rows = []
    for crime_i, ix_list in enumerate(idxs):
        for station_i in ix_list:
            rows.append((station_i, crime_i))

    df_links = pd.DataFrame(rows, columns=['station_idx', 'crime_idx'])
    crime_counts = df_links.groupby('station_idx').size().reset_index(name='crime_count')

    # Merge with station data
    df_stations = df_stations.copy()
    df_stations['station_idx'] = df_stations.index
    df_stations = df_stations.merge(crime_counts, on='station_idx', how='left')
    df_stations['crime_count'] = df_stations['crime_count'].fillna(0).astype(int)

    return df_stations

# Plot static Folium map
@st.cache_data
def plot_crime_density_map(radius_m=200, highlight_station=None):
    df_stations = get_crime_counts_per_station(radius_m=radius_m)
    df_bounds = get_alcaldia_boundaries()

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

    # Hexagon layer for crime density
    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=df_stations,
        get_position=["lon", "lat"],
        radius=radius_m,
        elevation_scale=100,
        elevation_range=[0, 1000],
        pickable=True,
        extruded=True,
        getElevationWeight="crime_count",
        elevationAggregation="SUM",
        colorRange=[
            [0, 0, 0],
            [173, 255, 47],
            [255, 215, 0],
            [255, 140, 0],
            [255, 69, 0],
            [139, 0, 0]
        ]
    )

    # Optional highlight layer
    highlight_layer = None
    if highlight_station is not None:
        highlight_layer = pdk.Layer(
            "ScatterplotLayer",
            data=[highlight_station.to_dict()],
            get_position=["lon", "lat"],
            get_radius=1000,
            get_color=[43, 125, 233],
            pickable=True
        )

    # Alcaldía boundary layer
    boundary_layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_data,
        stroked=True,
        filled=False,
        get_line_color=[80, 80, 80],
        line_width_min_pixels=1
    )

    view_state = pdk.ViewState(
        latitude=19.4,
        longitude=-99.1,
        zoom=11.5,
        pitch=0,
        bearing=0
    )

    layers = [boundary_layer, hex_layer]
    if highlight_layer:
        layers.append(highlight_layer)

    tooltip_config = {
        "html": (
        "<b>Robos:</b> {crime_count}<br />"
        "<b>Estación:</b> {nombre}"
        "<b>Estación:</b> {linea}"
        ),
    }

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="light",
        tooltip=tooltip_config
    )

# For search bar
def get_station_stats(station_name, radius_m=50):
    df_crimes = get_crimes()
    df_stations = get_metro_stations()

    # Match station by name
    match = df_stations[df_stations['nombre'].astype(str).str.contains(station_name, case=False)]
    if match.empty:
        return None, None

    station = match.iloc[0]
    station_coords = np.radians([[station['lat'], station['lon']]])
    crime_coords = np.radians(df_crimes[['latitud', 'longitud']].values)

    tree = BallTree(crime_coords, metric='haversine')
    r = radius_m / 6371000.0
    idxs = tree.query_radius(station_coords, r=r)[0]

    nearby_crimes = df_crimes.iloc[idxs].copy()
    nearby_crimes['hora'] = pd.to_datetime(nearby_crimes['hora_hecho']).dt.hour

    total = len(nearby_crimes)
    robos = nearby_crimes[nearby_crimes['delito'].str.contains('ROBO', case=False)]
    robo_count = len(robos)
    most_common_robo = robos['delito'].value_counts().idxmax() if not robos.empty else None
    avg_hour = int(nearby_crimes['hora'].mean()) if not nearby_crimes.empty else None

    stats = {
        "total_crimes": total,
        "robos": robo_count,
        "most_common_robo": most_common_robo,
        "avg_hour": avg_hour
    }

    return station, stats

# Crime comparison
def geocode_address(address):
    geolocator = Nominatim(user_agent="cdmx_crime_map")
    location = geolocator.geocode(f"{address}, Mexico City", timeout=10)
    if location:
        return {"lat": location.latitude, "lon": location.longitude, "name": location.address}
    return None

def get_crimes_near_point(lat, lon, radius_m=100):
    df_crimes = get_crimes()
    crime_coords = np.radians(df_crimes[['latitud', 'longitud']].values)
    point = np.radians([[lat, lon]])
    tree = BallTree(crime_coords, metric='haversine')
    r = radius_m / 6371000.0
    idxs = tree.query_radius(point, r=r)[0]
    nearby = df_crimes.iloc[idxs].copy()
    nearby['hora'] = pd.to_datetime(nearby['fecha_hecho']).dt.hour
    return nearby

def summarize_crimes(df):
    total = len(df)
    robos = df[df['delito'].str.contains('ROBO', case=False)]
    robo_count = len(robos)
    most_common_robo = robos['delito'].value_counts().idxmax() if not robos.empty else None
    avg_hour = int(df['hora'].mean()) if not df.empty else None
    return {
        "total_crimes": total,
        "robos": robo_count,
        "most_common_robo": most_common_robo,
        "avg_hour": avg_hour
    }

def plot_comparison_map(station_coords, station_name, address_coords, address_label):
    m = folium.Map(location=[19.4326, -99.1332], zoom_start=11, tiles="CartoDB positron")

    folium.CircleMarker(
        location=station_coords,
        radius=10,
        color="#2B7DE9",
        fill=True,
        fill_opacity=0.9,
        popup=f"<b>Estación:</b> {station_name}"
    ).add_to(m)

    folium.CircleMarker(
        location=address_coords,
        radius=10,
        color="#2BDE73",
        fill=True,
        fill_opacity=0.9,
        popup=f"<b>Dirección:</b> {address_label}"
    ).add_to(m)

    return m