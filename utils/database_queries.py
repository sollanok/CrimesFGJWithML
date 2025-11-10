import duckdb
import pandas as pd
import streamlit as st

DB_PATH = "data/crimes_FGJ.db"

def get_connection():
    return duckdb.connect(DB_PATH)

def run_query(query: str) -> pd.DataFrame:
    con = get_connection()
    try:
        df = con.execute(query).fetchdf()
        return df
    finally:
        con.close()

# ----------------------------
# ---------- EDA -------------
# ----------------------------
@st.cache_data
def get_crimes_near_stations(radius_m=50):
    query = """
    SELECT latitud, longitud, delito, fecha_hecho, hora_hecho
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    """
    return run_query(query)

@st.cache_data
def get_metro_stations():
    query = """
    SELECT nombre, linea, lat, lon
    FROM lineas_metro
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    """
    return run_query(query)

@st.cache_data
def get_robbery_counts_by_borough():
    query = """
    SELECT alcaldia_hecho, COUNT(*) as robbery_count
    FROM crimes_clean
    WHERE delito LIKE '%ROBO%'
    AND alcaldia_hecho IS NOT NULL
    GROUP BY alcaldia_hecho
    ORDER BY robbery_count DESC
    """
    return run_query(query)

@st.cache_data
def get_physical_crimes():
    query = """
    SELECT
    EXTRACT(hour FROM hora_hecho::TIME) AS hour,
    strftime(fecha_hecho, '%A') AS day_of_week
    FROM crimes_clean
    WHERE delito IN (
    'ROBO A PASAJERO A BORDO DE TAXI CON VIOLENCIA',
    'ROBO A TRANSEUNTE EN VIA PUBLICA CON VIOLENCIA',
    'ROBO DE VEHICULO DE SERVICIO PARTICULAR CON VIOLENCIA',
    'ROBO A NEGOCIO CON VIOLENCIA',
    'ROBO A CASA HABITACION CON VIOLENCIA',
    'ROBO A REPARTIDOR CON VIOLENCIA',
    'ROBO A PASAJERO A BORDO DE MICROBUS CON VIOLENCIA',
    'ROBO A PASAJERO A BORDO DEL METRO CON VIOLENCIA',
    'ROBO A TRANSPORTISTA CON VIOLENCIA',
    'LESIONES INTENCIONALES',
    'LESIONES INTENCIONALES POR GOLPES',
    'LESIONES INTENCIONALES POR ARMA BLANCA',
    'LESIONES INTENCIONALES POR ARMA DE FUEGO',
    'HOMICIDIO CULPOSO',
    'HOMICIDIO DOLOSO',
    'HOMICIDIO',
    'HOMICIDIO POR GOLPES',
    'HOMICIDIO POR ARMA BLANCA',
    'HOMICIDIO POR ARMA DE FUEGO',
    'TENTATIVA DE HOMICIDIO',
    'FEMINICIDIO',
    'FEMINICIDIO POR GOLPES',
    'FEMINICIDIO POR ARMA DE FUEGO'
    )
    AND hora_hecho IS NOT NULL
    AND fecha_hecho IS NOT NULL
    """
    return run_query(query)

@st.cache_data
def get_hourly_robberies():
    query = """
    SELECT
    EXTRACT(hour FROM hora_hecho::TIME) AS hour,
    EXTRACT(dow FROM fecha_hecho::DATE) AS weekday
    FROM crimes_clean
    WHERE delito IN (
    'ROBO A PASAJERO A BORDO DE TAXI CON VIOLENCIA',
    'ROBO A TRANSEUNTE EN VIA PUBLICA CON VIOLENCIA',
    'ROBO DE VEHICULO DE SERVICIO PARTICULAR CON VIOLENCIA',
    'ROBO A NEGOCIO CON VIOLENCIA',
    'ROBO A CASA HABITACION CON VIOLENCIA',
    'ROBO A REPARTIDOR CON VIOLENCIA',
    'ROBO A PASAJERO A BORDO DE MICROBUS CON VIOLENCIA',
    'ROBO A PASAJERO A BORDO DEL METRO CON VIOLENCIA',
    'ROBO A TRANSPORTISTA CON VIOLENCIA'
    )
    AND hora_hecho IS NOT NULL
    AND fecha_hecho IS NOT NULL
    """
    return run_query(query)


# ----------------------------
# ------ VISUALIZATION -------
# ----------------------------
@st.cache_data
def get_alcaldia_boundaries():
    query = """
    SELECT
      "properties.NOMGEO" AS nombre,
      "geometry.type" AS geom_type,
      "geometry.coordinates" AS coordinates
    FROM limites_alcaldias
    WHERE "geometry.type" IN ('Polygon', 'MultiPolygon')
    """
    return run_query(query)

