#-------------------------------
#-----------Imports-----------
#-------------------------------
import pandas as pd
from unidecode import unidecode
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap
import os
from folium import plugins
import streamlit as st
from streamlit.components.v1 import html

#-------------------------------
#-------Initial Cleaning-------
#-------------------------------
# Load all data
@st.cache_data
def load_data():
  try:
    df = pd.read_csv('data/carpetasFGJ_acumulado_2025_01.csv')
    boroughs_coordinates = 'data/alcaldias_cdmx.geojson'
    metro_coordinates = 'data/estaciones_metro.geojson'
    print("Data loaded successfully.")
  except FileNotFoundError:
    print(f"Error: One or more files were not found.")
    df = None
  except Exception as e:
    print(f"An error occurred while loading the data: {e}")
    df = None
  return df, boroughs_coordinates, metro_coordinates

# Use the strip_accents_upper function from the previous period
def strip_accents_upper(text):
  return unidecode(str(text)).upper().strip() if pd.notna(text) else text

@st.cache_data
def clean_data(df):  
  if df is not None:
    # Standardize date and time formats
    if 'fecha_hecho' in df.columns:
      df['fecha_hecho'] = pd.to_datetime(df['fecha_hecho'], errors='coerce')
      print("fecha_hecho format standardized.")
    else:
      print("Column 'fecha_hecho' not found in the dataframe.")
    if 'hora_hecho' in df.columns:
      try:
        df['hora_hecho_dt'] = pd.to_datetime(df['hora_hecho'], format='%H:%M:%S', errors='coerce').dt.time
      except Exception as e:
        df['hora_hecho_dt'] = pd.to_datetime(df['hora_hecho'], errors='coerce').dt.time
        print(f"Could not parse time with format 'HH:MM:SS'. Error: {e}")
        print("hora_hecho format standardized.")
    else:
      print("Column 'hora_hecho' not found in the dataframe.")

  # Normalize categorical text (delito, alcaldia_hecho, colonia_hecho)
  categorical_cols = ['delito', 'alcaldia_hecho', 'colonia_hecho']
  for col in categorical_cols:
    if col in df.columns:
      # Impute missing categories
      df[col + '_N'] = df[col].apply(strip_accents_upper)
      df[col + '_N'] = df[col + '_N'].fillna('UNKNOWN')
      print(f"Categorical text in '{col}' normalized.")
    else:
      print(f"Column '{col}' not found in the dataframe.")

  # Remove duplicates
  initial_rows = len(df)
  df.drop_duplicates(inplace=True)
  rows_after_duplicates = len(df)
  print(f"Removed {initial_rows - rows_after_duplicates} duplicate rows.")

  # Remove rows with missing critical fields
  critical_columns = ['fecha_hecho', 'hora_hecho', 'delito', 'alcaldia_hecho']
  df.dropna(subset=critical_columns, inplace=True)
  rows_after_missing = len(df)
  print(f"Removed {rows_after_duplicates - rows_after_missing} \
 rows with missing critical data.")
  
  # Keep only valid years (2016–2024)
  df = df[
    (df['fecha_hecho'].dt.year >= 2016) &
    (df['fecha_hecho'].dt.year <= 2024)
  ]
  
  rows_after_year_filter = len(df)
  print(f"Filtered crimes to include only records from 2016 to 2024. Remaining rows: {rows_after_year_filter}")

  # Use normalize to compare dates only
  rows_after_future_dates = len(df)
  print(f"Removed {rows_after_missing - rows_after_future_dates}\
 rows with future dates.")
  
  # Clean coordinate columns
  if {'latitud', 'longitud'}.issubset(df.columns):
    # Drop invalid entries and convert to float
    df['latitud'] = pd.to_numeric(df['latitud'], errors='coerce')
    df['longitud'] = pd.to_numeric(df['longitud'], errors='coerce')
    initial_rows_geo = len(df)
    # Get CDMX bound coordinates only.
    df = df[
        df['latitud'].between(19.0, 19.6) &
        df['longitud'].between(-99.4, -98.9)
    ]
    print(f"Removed {initial_rows_geo - len(df)} rows with invalid coordinates.")

    # Drop unnecessary columns to aliviate computer burden
    cols_to_drop = [col for col in df.columns if df[col].isna().all()]
    if cols_to_drop:
      df.drop(columns=cols_to_drop, inplace=True)
      print(f"Dropped entirely empty columns: {cols_to_drop}")


  # Generate derived columns
  if 'fecha_hecho' in df.columns:
    df['Weekday'] = df['fecha_hecho'].dt.day_name()
    df['Month'] = df['fecha_hecho'].dt.month_name()
    df['Year'] = df['fecha_hecho'].dt.year
  if 'hora_hecho_dt' in df.columns:
    df['Hour'] = pd.to_datetime(df['hora_hecho_dt'],
                                     format='%H:%M:%S').dt.hour
  print("Derived columns (Weekday, Month, Year, Hour) created.")

  print("\nData cleaning and initial normalization steps complete.")
  print("\nDisplaying info of the cleaned data before full normalization:")
  print(df.info())
  
  return df

def get_year_range(df):
    return int(df['Year'].min()), int(df['Year'].max())
  
#-------------------------------
#--------Load All Years---------
#-------------------------------
@st.cache_data
def load_all_years():
  # Load raw data and geojson paths
  df_raw, _, _ = load_data()
    
  # Clean full dataset
  cleaned_df = clean_data(df_raw)
    
  # Get year range
  min_year, max_year = get_year_range(cleaned_df)
    
  # Split into yearly DataFrames
  yearly_dfs = {
    year: cleaned_df[cleaned_df['Year'] == year].reset_index(drop=True)
    for year in range(min_year, max_year + 1)
  }
    
  print(f"Loaded and split data for years {min_year} to {max_year}.")
  return yearly_dfs
  

#-------------------------------
#-----Preparing for Mapping-----
#-------------------------------
def create_map(year):
  # Load all years once
  yearly_data = load_all_years()

  # Check if the requested year exists
  if year not in yearly_data:
    print(f"Year {year} not found in data.")
    return

  # Use the cleaned DataFrame for the selected year
  cleaned_crimes_df = yearly_data[year]

  # Load geojson paths
  _, boroughs_coordinates, metro_coordinates = load_data()

  # Filter robbery-related crimes
  if 'delito' not in cleaned_crimes_df.columns:
    print("Error: 'delito' column missing from cleaned data.")
    return

  robberies_df = cleaned_crimes_df[
    cleaned_crimes_df['delito'].str.contains('ROBO', case=False, na=False)
  ]
  
  # Convert crimes DataFrame to GeoDataFrame
  crimes_gdf = gpd.GeoDataFrame(
    robberies_df,
    geometry=gpd.points_from_xy(robberies_df.longitud, robberies_df.latitud),
    crs="EPSG:4326"  # CDMX WGS84
  )
  
  # Load metro stations GeoJSON properly
  metro_stations_gdf = gpd.read_file(metro_coordinates)
  print(f"Loaded {len(metro_stations_gdf)} metro stations.")

  # Reproject both datasets to a metric CRS for buffering
  crimes_proj = crimes_gdf.to_crs(epsg=3857)
  metro_proj = metro_stations_gdf.to_crs(epsg=3857)

  # Create 50m buffers around metro stations
  metro_proj['buffer'] = metro_proj.buffer(50)

  # Convert buffer to a GeoDataFrame
  metro_buffer_gdf = gpd.GeoDataFrame(
      metro_proj[['nombre']],
      geometry=metro_proj['buffer'],
      crs=metro_proj.crs
  )

  # Spatial join: find crimes within each buffer
  joined = gpd.sjoin(crimes_proj, metro_buffer_gdf, predicate='within')

  # Count crimes per station
  station_crime_counts = joined.groupby('nombre').size().reset_index(name='crime_count')

  # Merge back with the metro GeoDataFrame
  metro_with_crimes = metro_stations_gdf.merge(station_crime_counts, on='nombre', how='left')
  metro_with_crimes['crime_count'] = metro_with_crimes['crime_count'].fillna(0)

  #-------------------------------
  #-------- Visualization --------
  #-------------------------------
  # Create folder if missing
  os.makedirs("output", exist_ok=True)

  # Create base map
  m = folium.Map(location=[19.4326, -99.1332], zoom_start=11, tiles="cartodbpositron")

  # Compute robberies near each metro station
  station_counts = []
  for idx, station in metro_stations_gdf.iterrows():
    nearby = crimes_gdf[
      crimes_gdf.geometry.within(station.geometry.buffer(0.00005))
    ]  # ~50m radius
    station_counts.append(
      {
        "nombre": station["nombre"],
        "lat": station.geometry.y,
        "lon": station.geometry.x,
        "robos": len(nearby),
      }
    )

  station_df = pd.DataFrame(station_counts)

  # Normalize robbery counts for circle sizing
  max_robos = station_df["robos"].max() if station_df["robos"].max() > 0 else 1
  station_df["radius"] = (station_df["robos"] / max_robos) * 40

  # Robbery frequency visualization
  robbery_layer = folium.FeatureGroup(name="Robberies near or in stations.", show=True)
  for _, row in station_df.iterrows():
    if row["robos"] == 0:
      color = "lightblue"
      radius = 3  # Minimum visible radius
    else:
      color = (
        "red"
        if row["robos"] > max_robos * 0.6
        else "orange"
        if row["robos"] > max_robos * 0.3
        else "green"
      )
      radius = row["radius"]

    folium.CircleMarker(
      location=[row["lat"], row["lon"]],
      radius=radius,
      color=color,
      fill=True,
      fill_opacity=0.6,
      popup=f"<b>{row['nombre']}</b><br>Robberies: {row['robos']}",
    ).add_to(robbery_layer)
  robbery_layer.add_to(m)

  # Add metro station markers
  metro_layer = folium.FeatureGroup(name="Metro stations", show=False)
  for _, row in metro_stations_gdf.iterrows():
    folium.Marker(
      location=[row.geometry.y, row.geometry.x],
      icon=folium.Icon(color="blue", icon="train", prefix="fa"),
      popup=f"<b>{row['nombre']}</b><br>{row['ubicacion']}",
    ).add_to(metro_layer)
  metro_layer.add_to(m)
  
  folium.GeoJson(
    boroughs_coordinates,
    name='Boroughs',
    style_function=lambda x: {'fillOpacity': 0, 'color': 'black', 'weight': 0.5}
  ).add_to(m)

  # Add layer control
  folium.LayerControl(collapsed=False).add_to(m)

  # Save map
  map_html = m._repr_html_()
  html(map_html, height=600, scrolling=True)

#-------------------------------
#------------Slider-------------
#-------------------------------
# Create slider functions
def year_slider(df, label="Slide to select a year"):
  min_year = int(df['Year'].min())
  max_year = int(df['Year'].max())
  selected_year = st.slider(label, min_year, max_year, min_year)
  return selected_year