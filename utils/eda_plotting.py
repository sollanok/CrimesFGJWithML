import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from shapely.geometry import Point
from sklearn.neighbors import BallTree
import streamlit as st

from utils.database_queries import (
    get_crimes_near_stations,
    get_metro_stations,
    get_robbery_counts_by_borough,
    get_physical_crimes,
    get_hourly_robberies
)

@st.cache_data
def compute_line_crime_stats(radius_m=50):
    # These functions will hit the cache after the first run
    df_crimes = get_crimes_near_stations()
    df_metro = get_metro_stations()
    
    # Convert to GeoDataFrames
    gdf_crimes = gpd.GeoDataFrame(df_crimes, geometry=gpd.points_from_xy(df_crimes['longitud'], df_crimes['latitud']), crs="EPSG:4326")
    gdf_metro = gpd.GeoDataFrame(df_metro, geometry=gpd.points_from_xy(df_metro['lon'], df_metro['lat']), crs="EPSG:4326")

    # Spatial proximity using BallTree
    A = np.radians(df_crimes[['latitud','longitud']].values)
    B = np.radians(df_metro[['lat','lon']].values)
    tree = BallTree(B, metric='haversine')
    
    # Calculate radius in radians
    r = radius_m / 6371000.0  
    idxs = tree.query_radius(A, r=r)

    # Map crimes to lines
    station_to_line = df_metro.reset_index().set_index('index')['linea'].to_dict()
    rows = []
    for crime_i, ix_list in enumerate(idxs):
        # Use a set to avoid double-counting if a crime is near
        # two stations on the same line
        lines_for_this_crime = {station_to_line[int(i)] for i in ix_list}
        for L in lines_for_this_crime:
            rows.append((crime_i, L))
            
    if not rows: # Handle case with no crimes found
        st.warning("No crimes found within the specified radius.")
        return pd.DataFrame() # Return empty frame

    df_cr_line = pd.DataFrame(rows, columns=['crime_idx','linea'])
    
    # Aggregate
    line_crimes = df_cr_line.groupby('linea')['crime_idx'].nunique().reset_index(name='crimes_near_line')
    line_st = df_metro.groupby('linea').size().reset_index(name='stations')
    
    # Buffer area per line
    gdf_metro_m = gdf_metro.to_crs("EPSG:32614") # Project to a CRS in meters
    gdf_metro_m['linea'] = df_metro['linea']
    gdf_line_buf = gdf_metro_m.buffer(radius_m)
    
    # Dissolve buffers by line
    gdf_line_union = gpd.GeoDataFrame({'linea': gdf_metro_m['linea']}, geometry=gdf_line_buf, crs="EPSG:32614").dissolve(by='linea')
    
    # Clip overlapping areas (this is the overlay part)
    # Note: This is still expensive but will only run ONCE.
    gdf_city = gpd.GeoSeries([gdf_line_union.unary_union], crs="EPSG:32614")
    gdf_line_clip = gpd.overlay(gdf_line_union.reset_index(), gpd.GeoDataFrame(geometry=gdf_city, crs="EPSG:32614"), how='intersection').set_index('linea')
    gdf_line_clip['area_m2'] = gdf_line_clip.area

    # Merge stats
    line_stats = (line_st
    .merge(line_crimes, on='linea', how='left')
    .merge(gdf_line_clip[['area_m2']], left_on='linea', right_index=True, how='left')
    .fillna({'crimes_near_line':0, 'area_m2':0})
    .reset_index(drop=True))
    
    line_stats['area_km2'] = line_stats['area_m2'] / 1e6
    line_stats['crimes_per_km2'] = line_stats.apply(
        lambda r: r['crimes_near_line']/r['area_km2'] if r['area_km2']>0 else np.nan,
        axis=1
    )
    
    return line_stats


def plot_near_stations():
    line_stats = compute_line_crime_stats(radius_m=50)
    
    if line_stats.empty:
        return # Don't plot if there's no data

    col1, col2 = st.columns(2)
    with col1:
        fig1, ax1 = plt.subplots(figsize=(6, 6)) # Use fig, ax
        order = line_stats.sort_values('crimes_near_line', ascending=False)['linea']
        ax1.barh(
            order,
            line_stats.set_index('linea').loc[order, 'crimes_near_line'],
            color="#A62639"
        )
        ax1.set_title("Crímenes ≤50 m por línea del metro")
        ax1.set_xlabel("Crímenes")
        ax1.set_ylabel("Línea del metro")
        fig1.tight_layout()
        st.pyplot(fig1) # Pass the fig object
        # plt.clf() is not needed if you pass the fig object

    with col2:
        fig2, ax2 = plt.subplots(figsize=(6, 6)) # Use fig, ax
        order = line_stats.sort_values('crimes_per_km2', ascending=False)['linea']
        ax2.barh(
            order,
            line_stats.set_index('linea').loc[order, 'crimes_per_km2'],
            color="#A62639")
        ax2.set_title("Densidad de crimen (≤50 m) por línea [crímenes/km²]")
        ax2.set_xlabel("Crímenes por km²")
        ax2.set_ylabel("Línea")
        fig2.tight_layout()
        st.pyplot(fig2) # Pass the fig object


def autopct_format(values):
    """
    Helper function to format the autopct labels in the pie chart
    to show both percentage and the absolute value.
    """
    def my_format(pct):
        total = sum(values)
        val = int(round(pct * total / 100.0))
        return f'{pct:.1f}%\n({val:,})'
    return my_format

def plot_robbery_pie_chart():
    df = get_robbery_counts_by_borough()

    if df.empty:
        st.warning("No robbery data found.")
        return

    # Set 'alcaldia_hecho' as index to create a Series for plotting
    borough_counts = df.set_index('alcaldia_hecho')['robbery_count']

    # Get top 5
    top_boroughs = borough_counts.nlargest(5)

    # Get the #1 borough for the title
    top_borough = top_boroughs.index[0]
    top_value = top_boroughs.iloc[0]

    # Define colors for the pie chart
    colors = ['#A62639', '#FFD166', '#06D6A0', '#118AB2', '#073B4C']
    
    # --- PIE CHART with boxed title ---
    fig, ax = plt.subplots(figsize=(10, 10))
    
    ax.pie(
        top_boroughs.values,
        labels=top_boroughs.index,
        autopct=autopct_format(top_boroughs.values),
        startangle=140,
        colors=colors,
        textprops={'fontsize': 12, 'weight': 'bold'}
    )

    ax.set_title(
        f'Total de robos en las alcaldías con más incidencias\nTop: {top_borough} ({top_value:,} robos)',
        fontsize=18, fontweight='bold',
        bbox=dict(facecolor='lightgrey', edgecolor='black', boxstyle='round,pad=0.5')
    )
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    fig.tight_layout()
    
    st.pyplot(fig)

@st.cache_data
def compute_heatmap_data():
    df_physical = get_physical_crimes()
    
    if df_physical.empty:
        return pd.DataFrame(), 0.0

    # Calculate average crimes from 19 to 21 hours
    evening_hours = df_physical[df_physical['hour'].isin([19, 20, 21])]
    
    avg_evening_crimes = 0.0
    if not evening_hours.empty:
        # Check if 'hour' column has data before grouping
        if 'hour' in evening_hours.columns:
            avg_evening_crimes = (
                evening_hours.groupby('hour')
                             .size()
                             .mean()
            )
        
    # Create count table by day of week and hour
    heatmap_data = (
        df_physical.groupby(['day_of_week', 'hour'])
                   .size()
                   .unstack(fill_value=0)
    )

    # Ensure all 24 hours are present (from 0 to 23)
    all_hours = list(range(24))
    for hour in all_hours:
        if hour not in heatmap_data.columns:
            heatmap_data[hour] = 0
    heatmap_data = heatmap_data[all_hours] # Sort columns

    # Ensure the days are in correct order
    day_order = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday',
        'Friday', 'Saturday', 'Sunday'
    ]
    heatmap_data = heatmap_data.reindex(day_order, fill_value=0)
    
    return heatmap_data, avg_evening_crimes

def plot_crime_heatmap():
    heatmap_data, avg_evening_crimes = compute_heatmap_data()
    
    if heatmap_data.empty:
        st.warning("No data found for physical crimes heatmap.")
        return

    # Display the average crimes metric
    st.metric(
        label="Promedio de crímenes físicos por hora (12 PM - 12 AM)",
        value=f"{avg_evening_crimes:.2f}"
    )

    # Plot heatmap
    fig, ax = plt.subplots(figsize=(18, 7))
    sns.heatmap(
        heatmap_data,
        cmap="Reds",
        annot=True,
        fmt="d",
        cbar_kws={'label': 'Total de crímenes físicos'},
        annot_kws={"size": 8},
        ax=ax
    )
    ax.set_title(
        "Mapa de calor de crímenes con aspecto físico (2015-2024)",
        fontsize=16,
        fontweight='bold'
    )
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Día de la semana")
    
    st.pyplot(fig)

def plot_hourly_robberies():
    df = get_hourly_robberies()
    WEEKDAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    profiles = {}
    for wd in range(7):
        s = (df[df['weekday'] == wd]['hour']
             .value_counts()
             .reindex(range(24), fill_value=0)
             .sort_index())
        profiles[wd] = s

    colors = ['#3D85C6','#2F5597','#FF6F61','#6AA84F','#8E7CC3','#F6B26B','#C0504D']
    plt.figure(figsize=(12, 6), dpi=140)
    for wd, col in zip(range(7), colors):
        plt.plot(profiles[wd].index, profiles[wd].values, marker='o', linewidth=2,
                 label=WEEKDAYS_SHORT[wd], color=col)

    plt.title("Hourly Robberies by Day of Week (CDMX)", fontsize=15, pad=12)
    plt.xlabel("Hour of Day", fontsize=12)
    plt.ylabel("Number of Robberies", fontsize=12)
    plt.xticks(range(0, 24))
    plt.legend(ncol=3, frameon=False)
    plt.grid(True, alpha=0.35)
    plt.tight_layout()
    st.pyplot(plt.gcf())
    plt.clf()
