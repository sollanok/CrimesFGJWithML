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
import time
import ssl
import certifi
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

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
def plot_crime_density_map(radius_m=100, highlight_station=None):
    df_stations = get_crime_counts_per_station(radius_m=radius_m)
    df_bounds = get_alcaldia_boundaries()

    m = folium.Map(location=[19.3300, -99.1032], zoom_start=10, tiles="CartoDB positron")

    # Add alcaldía boundaries
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
                # Ensure each point is a list of two floats (query returns NumPy array)
                points = [(float(lat), float(lon)) for lon, lat in ring]
                folium.Polygon(
                    locations=points,
                    color="#555",
                    weight=1,
                    fill=True,
                    fill_opacity=0.05,
                    popup=f"Alcaldía: {row['nombre']}"
                ).add_to(m)

        except Exception as e:
            print(f"Error drawing polygon: {e}")

    crime_layers = {
        "no_robberies": folium.FeatureGroup(name="0 robos", show=True),
        "low_robberies": folium.FeatureGroup(name="Menos de 100 robos (Bajo)", show=True),
        "medium_robberies": folium.FeatureGroup(name="Menos de 300 robos (Medio)", show=True),
        "high_robberies": folium.FeatureGroup(name="Menos de 500 robos (Alto)", show=True),
        "very_high_robberies": folium.FeatureGroup(name="Menos de 800 Robos (Muy Alto)", show=True),
        "extreme_robberies": folium.FeatureGroup(name="800+ robos (Extremo)", show=True)
    }
    
    for _, row in df_stations.iterrows():
        count = row['crime_count']
        
        popup = folium.Popup(f"<b>Línea del metro:</b> {row['linea']:.0f}<br><b>Robos:</b> {count:.0f}", max_width=250)
        radius = 3 + count**0.2
        
        if count == 0:
            color = "#00000034"
            radius = 3
            target_layer = crime_layers["no_robberies"]
            
        elif count < 100:
            color = "#C4E10D"
            target_layer = crime_layers["low_robberies"]
            
        elif count < 300:
            color = "#F2D324"
            target_layer = crime_layers["medium_robberies"]
            
        elif count < 500:
            color = "#FF9502"
            target_layer = crime_layers["high_robberies"]
            
        elif count < 800:
            color = "#E86020"
            target_layer = crime_layers["very_high_robberies"]
            
        else:
            color = "#B12B2B"
            target_layer = crime_layers["extreme_robberies"]
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.6,
            popup=popup
        ).add_to(target_layer)

    for layer in crime_layers.values():
        layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    if highlight_station is not None:
        folium.CircleMarker(
            location=[highlight_station['lat'], highlight_station['lon']],
            radius=10,
            color="#2B7DE9",
            fill=True,
            fill_opacity=0.9,
            popup=folium.Popup(f"<b>Estación {highlight_station['nombre']}</b><br>Línea: {highlight_station['linea']}", max_width=250)
        ).add_to(m)

    return m

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
    # --- SSL fix by Gemini ---
    # 1. Create a default SSL context that uses certifi's certificates
    ctx = ssl.create_default_context(cafile=certifi.where())
    
    # 2. Pass the 'ssl_context=ctx' when you create the geolocator
    geolocator = Nominatim(
        user_agent="cdmx_crime_map",
        ssl_context=ctx  # This line is the key
    )
    # -----------------------

    try:
        # Respect the 1-request-per-second policy
        time.sleep(1) 
        
        location = geolocator.geocode(f"{address}, Mexico City", timeout=10)
        
        if location:
            return {"lat": location.latitude, "lon": location.longitude, "name": location.address}
        return None
    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
        print(f"Error geocoding {address}: {e}")
        return None

def get_crimes_near_point(lat, lon, radius_m=100):
    df_crimes = get_crimes()
    crime_coords = np.radians(df_crimes[['latitud', 'longitud']].values)
    point = np.radians([[lat, lon]])
    tree = BallTree(crime_coords, metric='haversine')
    r = radius_m / 6371000.0
    idxs = tree.query_radius(point, r=r)[0]
    nearby = df_crimes.iloc[idxs].copy()
    nearby['hora'] = pd.to_datetime(nearby['hora_hecho']).dt.hour
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