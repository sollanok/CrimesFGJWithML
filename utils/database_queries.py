import duckdb
import pandas as pd
import streamlit as st

DB_PATH = "data/crimes_FGJ.db"

def get_connection():
    return duckdb.connect(DB_PATH)

def run_query(query: str) -> pd.DataFrame:
    con = get_connection()
    con.execute("LOAD spatial;")
    try:
        df = con.execute(query).fetchdf()
        return df
    finally:
        con.close()

# ----------------------------
# ---------- EDA -------------
# ----------------------------
@st.cache_data
def get_crimes(radius_m=100):
    query = """
    SELECT latitud, longitud, delito, fecha_hecho, hora_hecho, anio_hecho
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    """
    return run_query(query)

@st.cache_data
def get_metro_stations():
    query = """
    SELECT nombre, linea, lat, lon
    FROM lines_metro
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
    FROM borough_limits
    WHERE "geometry.type" IN ('Polygon', 'MultiPolygon')
    """
    return run_query(query)

@st.cache_data
def get_crimes_by_year(radius_m=100, year=None):
    year_filter = f"AND CAST(anio_hecho AS INT) = {year}" if year else ""
    query = f"""
    SELECT latitud, longitud, delito, fecha_hecho, hora_hecho, mes_hecho
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    {year_filter}
    """
    return run_query(query)

@st.cache_data
def get_affluence_density():
    query = """
    SELECT 
        s.num AS station_id,
        s.nombre AS station_name,
        s.lat,
        s.lon,
        SUM(a.afluencia) AS total_afluence
    FROM daily_affluence a
    JOIN lines_metro s ON a.key = s.num
    WHERE CAST(a.fecha AS DATE) BETWEEN DATE '2016-01-01' AND DATE '2024-12-31'
    GROUP BY s.num, s.nombre, s.lat, s.lon
    ORDER BY total_afluence DESC
    """
    return run_query(query)

@st.cache_data
def get_top_crime_stations(n=5):
    query = """
    SELECT s.nombre AS estacion, COUNT(*) AS crime_count
    FROM crimes_clean c
    JOIN lines_metro s ON ST_Distance(
        ST_Point(c.longitud, c.latitud),
        ST_Point(s.lon, s.lat)
    ) <= 100
    WHERE c.latitud IS NOT NULL AND c.longitud IS NOT NULL
    GROUP BY s.nombre
    ORDER BY crime_count DESC
    LIMIT {}
    """.format(n)
    return run_query(query)

@st.cache_data
def get_top_robo_stations(n=5):
    query = """
    SELECT s.nombre AS estacion, COUNT(*) AS robo_count
    FROM crimes_clean c
    JOIN lines_metro s ON ST_Distance(
        ST_Point(c.longitud, c.latitud),
        ST_Point(s.lon, s.lat)
    ) <= 100
    WHERE c.latitud IS NOT NULL AND c.longitud IS NOT NULL
    AND c.delito ILIKE '%ROBO%'
    GROUP BY s.nombre
    ORDER BY robo_count DESC
    LIMIT {}
    """.format(n)
    return run_query(query)

@st.cache_data
def get_top_affluence_stations(n=5):
    query = """
    SELECT s.nombre AS estacion, SUM(a.afluencia) AS total_afluence
    FROM daily_affluence a
    JOIN lines_metro s ON a.key = s.num
    WHERE CAST(a.fecha AS DATE) BETWEEN DATE '2016-01-01' AND DATE '2024-12-31'
    GROUP BY s.nombre
    ORDER BY total_afluence DESC
    LIMIT {}
    """.format(n)
    return run_query(query)

@st.cache_data
def get_station_coords(nombre):
    query = f"""
    SELECT lat, lon
    FROM lines_metro
    WHERE nombre = '{nombre}'
    """
    return run_query(query).iloc[0]

@st.cache_data
def get_total_crimes_station(nombre, radius_m=100):
    coords = get_station_coords(nombre)
    query = f"""
    SELECT COUNT(*) AS total_crimes
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    AND ST_Distance_Sphere( -- FIXED: Spherical distance in meters
        ST_Point(longitud, latitud),
        ST_Point({coords['lon']}, {coords['lat']})
    ) <= {radius_m}
    """
    return run_query(query).iloc[0]["total_crimes"]

@st.cache_data
def get_total_robos_station(nombre, radius_m=100):
    coords = get_station_coords(nombre)
    query = f"""
    SELECT COUNT(*) AS total_robos
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    AND delito ILIKE '%robo%'
    AND ST_Distance_Sphere( -- FIXED: Spherical distance in meters
        ST_Point(longitud, latitud),
        ST_Point({coords['lon']}, {coords['lat']})
    ) <= {radius_m}
    """
    return run_query(query).iloc[0]["total_robos"]

@st.cache_data
def get_most_common_robo_station(nombre, radius_m=100):
    coords = get_station_coords(nombre)
    query = f"""
    SELECT delito, COUNT(*) AS count
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    AND delito ILIKE '%robo%'
    AND ST_Distance_Sphere( -- FIXED: Spherical distance in meters
        ST_Point(longitud, latitud),
        ST_Point({coords['lon']}, {coords['lat']})
    ) <= {radius_m}
    GROUP BY delito
    ORDER BY count DESC
    LIMIT 1
    """
    return run_query(query).iloc[0]["delito"]

@st.cache_data
def get_average_time_station(nombre, radius_m=100):
    coords = get_station_coords(nombre)
    query = f"""
    SELECT AVG(EXTRACT(HOUR FROM hora_hecho::TIME)) AS avg_hour,
            AVG(EXTRACT(MINUTE FROM hora_hecho::TIME)) AS avg_minute
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    AND ST_Distance_Sphere( -- FIXED: Spherical distance in meters
        ST_Point(longitud, latitud),
        ST_Point({coords['lon']}, {coords['lat']})
    ) <= {radius_m}
    """
    return run_query(query).iloc[0]

@st.cache_data
def get_hotspot_coords_station(nombre, radius_m=100):
    coords = get_station_coords(nombre)
    query = f"""
    SELECT longitud, latitud, COUNT(*) AS count
    FROM crimes_clean
    WHERE latitud IS NOT NULL AND longitud IS NOT NULL
    AND ST_Distance_Sphere( -- FIXED: Spherical distance in meters
        ST_Point(longitud, latitud),
        ST_Point({coords['lon']}, {coords['lat']})
    ) <= {radius_m}
    GROUP BY longitud, latitud
    ORDER BY count DESC
    LIMIT 1
    """
    return run_query(query).iloc[0]

@st.cache_data
def get_crime_counts_per_station(radius_m=100):
    query = f"""
    SELECT
        s.num,
        s.linea,
        s.nombre,
        s.lat,
        s.lon,
        COUNT(c.*) AS crime_count
    FROM lines_metro s
    JOIN crimes_clean c
        ON c.latitud IS NOT NULL AND c.longitud IS NOT NULL
        AND ST_Distance_Sphere( -- Forces spherical distance calculation in meters
            ST_Point(c.longitud, c.latitud), -- Simplest point creation (lon, lat)
            ST_Point(s.lon, s.lat)          -- Simplest point creation (lon, lat)
        ) <= {radius_m} -- Distance is guaranteed to be in meters
    GROUP BY s.num, s.linea, s.nombre, s.lat, s.lon;
    """
    return run_query(query)