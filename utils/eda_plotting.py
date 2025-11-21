
import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.neighbors import BallTree
import streamlit as st
import plotly.express as px

from utils.database_queries import (
    get_crimes,
    get_metro_stations,
    get_robbery_counts_by_borough,
    get_physical_crimes,
    get_hourly_robberies
)

@st.cache_data
def compute_line_crime_stats(radius_m=50):
    df_crimes = get_crimes()
    df_metro = get_metro_stations()
    
    gdf_crimes = gpd.GeoDataFrame(df_crimes, geometry=gpd.points_from_xy(df_crimes['longitud'], df_crimes['latitud']), crs="EPSG:4326")
    gdf_metro = gpd.GeoDataFrame(df_metro, geometry=gpd.points_from_xy(df_metro['lon'], df_metro['lat']), crs="EPSG:4326")

    A = np.radians(df_crimes[['latitud','longitud']].values)
    B = np.radians(df_metro[['lat','lon']].values)
    tree = BallTree(B, metric='haversine')
    
    r = radius_m / 6371000.0  
    idxs = tree.query_radius(A, r=r)

    station_to_line = df_metro.reset_index().set_index('index')['linea'].to_dict()
    rows = []
    for crime_i, ix_list in enumerate(idxs):
        lines_for_this_crime = {station_to_line[int(i)] for i in ix_list}
        for L in lines_for_this_crime:
            rows.append((crime_i, L))
            
    if not rows:
        st.warning("No crimes found within the specified radius.")
        return pd.DataFrame()

    df_cr_line = pd.DataFrame(rows, columns=['crime_idx','linea'])
    
    line_crimes = df_cr_line.groupby('linea')['crime_idx'].nunique().reset_index(name='crimes_near_line')
    line_st = df_metro.groupby('linea').size().reset_index(name='stations')
    
    gdf_metro_m = gdf_metro.to_crs("EPSG:32614")
    gdf_metro_m['linea'] = df_metro['linea']
    gdf_line_buf = gdf_metro_m.buffer(radius_m)
    
    gdf_line_union = gpd.GeoDataFrame({'linea': gdf_metro_m['linea']}, geometry=gdf_line_buf, crs="EPSG:32614").dissolve(by='linea')
    
    gdf_city = gpd.GeoSeries([gdf_line_union.unary_union], crs="EPSG:32614")
    gdf_line_clip = gpd.overlay(gdf_line_union.reset_index(), gpd.GeoDataFrame(geometry=gdf_city, crs="EPSG:32614"), how='intersection').set_index('linea')
    gdf_line_clip['area_m2'] = gdf_line_clip.area

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
    try:
        line_stats = compute_line_crime_stats(radius_m=50)
    except NameError:
        st.error("Error: Function 'compute_line_crime_stats' undefined.")
        return
    
    if line_stats.empty:
        st.info("Not enough data.")
        return

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### Crímenes ≤50 m por línea del metro")

        order_1 = line_stats.sort_values('crimes_near_line', ascending=False)['linea'].tolist()
        
        fig1 = px.bar(
            line_stats,
            x='crimes_near_line',
            y='linea',
            orientation='h',
            labels={'crimes_near_line': 'Total de Crímenes', 'linea': 'Línea del metro'},
            category_orders={"linea": order_1}
        )
        
        fig1.update_layout(yaxis={'autorange': "reversed"},
                           paper_bgcolor='rgba(0,0,0,0)',
                           plot_bgcolor='rgba(0,0,0,0)'
                           )
        fig1.update_traces(marker_color='#E7BB67')
        fig1.update_yaxes(title_text="Línea del metro", automargin=True)
        
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("##### Densidad de crimen por línea")
        
        order_2 = line_stats.sort_values('crimes_per_km2', ascending=False)['linea'].tolist()

        fig2 = px.bar(
            line_stats,
            x='crimes_per_km2',
            y='linea',
            orientation='h',
            labels={'crimes_per_km2': 'Crímenes por km²', 'linea': 'Línea'},
            category_orders={"linea": order_2}
        )

        fig2.update_layout(yaxis={'autorange': "reversed"},
                           paper_bgcolor='rgba(0,0,0,0)',
                           plot_bgcolor='rgba(0,0,0,0)'
                           )
        fig2.update_traces(marker_color='#9F2241')
        fig2.update_yaxes(title_text="Línea del metro", automargin=True)

        st.plotly_chart(fig2, use_container_width=True)

def plot_robbery_pie_chart():
    try:
        df = get_robbery_counts_by_borough()
    except NameError:
        st.error("Error: La función 'get_robbery_counts_by_borough' no está definida.")
        return

    if df.empty:
        st.warning("No se encontraron datos de robos.")
        return

    df_sorted = df.sort_values(by='robbery_count', ascending=False)
    top_5_boroughs = df_sorted.head(5)

    top_borough = top_5_boroughs['alcaldia_hecho'].iloc[0]
    top_value = top_5_boroughs['robbery_count'].iloc[0]

    plotly_colors = ['#9F2241', '#E7BB67', "#6F58D2", '#474B24', '#0C7C59']
    
    fig = px.pie(
        top_5_boroughs,
        values='robbery_count',
        names='alcaldia_hecho',
        title=f'Total de robos en las alcaldías con más incidencias<br>Top: {top_borough} ({top_value:,} robos)',
        color_discrete_sequence=plotly_colors,
        height=600
    )

    fig.update_traces(
        textinfo='label+percent',
        textfont_size=14,
        hoverinfo='label+value+percent'
    )
    
    fig.update_layout(
        title_x=0.5,
        title_font_size=20,
        margin=dict(t=100, b=0, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)

@st.cache_data
def compute_heatmap_data():
    df_physical = get_physical_crimes()
    
    if df_physical.empty:
        return pd.DataFrame(), 0.0

    evening_hours = df_physical[df_physical['hour'].isin([19, 20, 21])]
    
    avg_evening_crimes = 0.0
    if not evening_hours.empty:
        if 'hour' in evening_hours.columns:
            avg_evening_crimes = (
                evening_hours.groupby('hour')
                             .size()
                             .mean()
            )
        
    heatmap_data = (
        df_physical.groupby(['day_of_week', 'hour'])
                   .size()
                   .unstack(fill_value=0)
    )

    all_hours = list(range(24))
    for hour in all_hours:
        if hour not in heatmap_data.columns:
            heatmap_data[hour] = 0
    heatmap_data = heatmap_data[all_hours]

    day_order = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday',
        'Friday', 'Saturday', 'Sunday'
    ]
    heatmap_data = heatmap_data.reindex(day_order, fill_value=0)
    
    return heatmap_data, avg_evening_crimes

def plot_crime_heatmap():
    try:
        heatmap_data, avg_evening_crimes = compute_heatmap_data()
    except NameError:
        st.error("Error: Undefined 'compute_heatmap_data'.")
        return
    
    if heatmap_data.empty:
        st.warning("No data found for physical crimes heatmap.")
        return
    
    st.metric(
        label="Promedio de crímenes físicos por hora (12 PM - 12 AM)",
        value=f"{avg_evening_crimes:.2f}"
    )

    st.markdown("##### Mapa de calor de crímenes con aspecto físico (2016-2024)")
    fig = px.imshow(
        heatmap_data,
        color_continuous_scale="Reds",
        labels=dict(
            x="Hora del día", 
            y="Día de la semana", 
            color="Total de crímenes físicos"
        ),
        text_auto=True,
        aspect="auto"
    )

    fig.update_layout(
        margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    fig.update_xaxes(side="top", tickmode='linear', showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

import plotly.graph_objects as go

def plot_hourly_robberies():
    df = get_hourly_robberies()
    WEEKDAYS_SHORT = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
    colors = ['#9F2241', '#E7BB67', '#BD93BD', "#EC5656", '#0C7C59','#BCE784','#30C5FF']

    fig = go.Figure()

    for wd, col in zip(range(7), colors):
        hourly_counts = (
            df[df['weekday'] == wd]['hour']
            .value_counts()
            .reindex(range(24), fill_value=0)
            .sort_index()
        )

        fig.add_trace(go.Scatter(
            x=hourly_counts.index,
            y=hourly_counts.values,
            mode='lines+markers',
            name=WEEKDAYS_SHORT[wd],
            line=dict(color=col, width=2),
            marker=dict(size=6)
        ))

    fig.update_layout(
        title="Robos cada hora por día de la seman",
        xaxis_title="Hora del día (00-23)",
        yaxis_title="Número de robos",
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(t=60, b=40, l=40, r=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

