# !! This is NOT meant to run as a module.
# This was executed manually as an app setup.
import duckdb
import pandas as pd
import os
import json

from unidecode import unidecode

# Base path to the root of your project
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Path to the data folder
DATA_DIR = os.path.join(BASE_DIR, "data")

# File paths
DB_FILE = os.path.join(DATA_DIR, "crimes_FGJ.db")
CRIME_CSV = os.path.join(DATA_DIR, "carpetasFGJ_acumulado_2025_01.csv")
ALCALDIAS_GEOJSON = os.path.join(DATA_DIR, "alcaldias_cdmx.geojson")
ESTACIONES_GEOJSON = os.path.join(DATA_DIR, "estaciones_metro.geojson")
LIMITES_JSON = os.path.join(DATA_DIR, "limite-de-las-alcaldas.json")
LINEAS_CSV = os.path.join(DATA_DIR, "lineas_metro.csv")

# ----------------------------
# ---- Cleaning Functions ----
# ----------------------------
def strip_accents_upper(text):
    return unidecode(str(text)).upper().strip() if pd.notna(text) else text

def load_data():
    try:
        df = pd.read_csv(CRIME_CSV, low_memory=False)
        print("Data loaded successfully.")
        return df
    except FileNotFoundError:
        print("Error: File not found.")
        return None
    except Exception as e:
        print(f"Error while loading data: {e}")
        return None

def clean_data(df):  
    if df is None:
        return None

    # Standardize date and time
    df['fecha_hecho'] = pd.to_datetime(df.get('fecha_hecho'), errors='coerce')
    df['hora_hecho_dt'] = pd.to_datetime(df.get('hora_hecho'), errors='coerce').dt.time

    # Normalize text
    for col in ['delito', 'alcaldia_hecho', 'colonia_hecho']:
        if col in df.columns:
            df[col + '_N'] = df[col].apply(strip_accents_upper).fillna('UNKNOWN')

    # Drop duplicates and missing criticals
    df.drop_duplicates(inplace=True)
    df.dropna(subset=['fecha_hecho', 'hora_hecho', 'delito', 'alcaldia_hecho'], inplace=True)

    # Filter by year
    df = df[(df['fecha_hecho'].dt.year >= 2016) & (df['fecha_hecho'].dt.year <= 2024)]

    # Clean coordinates
    df['latitud'] = pd.to_numeric(df.get('latitud'), errors='coerce')
    df['longitud'] = pd.to_numeric(df.get('longitud'), errors='coerce')
    df = df[df['latitud'].between(19.0, 19.6) & df['longitud'].between(-99.4, -98.9)]

    # Drop empty columns
    df.drop(columns=[col for col in df.columns if df[col].isna().all()], inplace=True)

    # Derived columns
    df['Weekday'] = df['fecha_hecho'].dt.day_name()
    df['Month'] = df['fecha_hecho'].dt.month_name()
    df['Year'] = df['fecha_hecho'].dt.year
    df['Hour'] = pd.to_datetime(df['hora_hecho_dt'], format='%H:%M:%S', errors='coerce').dt.hour

    print("Data cleaned. Final shape:", df.shape)
    return df

# ----------------------------
# ---- Load CSV into DB ------
# ----------------------------
def create_database():
    df_raw = load_data()
    df_clean = clean_data(df_raw)

    if df_clean is None or df_clean.empty:
        print("No data to load.")
        return

    if os.path.exists(DB_FILE):
        print(f"DB file already exists.")

    print(f"Creating DuckDB in file '{DB_FILE}'..")

    try:
        con = duckdb.connect(DB_FILE)

        # Crimes CSV
        # Register cleaned DataFrame and create table
        con.register("df_clean", df_clean)
        con.execute("CREATE TABLE crimes_clean AS SELECT * FROM df_clean")
        print("Table 1: 'crimes_clean' CREATED")

        # Metro lines CSV
        try:
            df_lineas = pd.read_csv(LINEAS_CSV, encoding='latin1')
            df_lineas.dropna(how='all', inplace=True)
            df_lineas = df_lineas[df_lineas.apply(lambda row: row.count() > 1, axis=1)]
            con.register("df_lineas", df_lineas)
            con.execute("CREATE TABLE lineas_metro AS SELECT * FROM df_lineas")
            print("Table 2: 'lineas_metro' CREATED")
        except Exception as e:
            print(f"Error loading 'lineas_metro': {e}")
            
        # Alcaldías GeoJSON
        try:
            with open(ALCALDIAS_GEOJSON, encoding='utf-8') as f:
                raw = json.load(f)
        
            df_alcaldias = pd.json_normalize(raw['features'])
            df_alcaldias.dropna(how='all', inplace=True)
            con.register("df_alcaldias", df_alcaldias)
            con.execute("CREATE TABLE alcaldias_cdmx AS SELECT * FROM df_alcaldias")
            print("✓ Table 3: 'alcaldias_cdmx' CREATED")
        except Exception as e:
            print(f"Error loading 'estaciones_metro': {e}")
        
        # Estaciones Metro GeoJSON
        try:
            df_estaciones = pd.read_json(ESTACIONES_GEOJSON)
            df_estaciones.dropna(how='all', inplace=True)
            con.register("df_estaciones", df_estaciones)
            con.execute("CREATE TABLE estaciones_metro AS SELECT * FROM df_estaciones")
            print("Table 4: 'estaciones_metro' CREATED")
        except Exception as e:
            print(f"Error loading 'estaciones_metro': {e}")
            
        # Límites de alcaldías JSON
        try:
            with open(LIMITES_JSON, encoding='utf-8') as f:
                raw = json.load(f)
            # If it's a GeoJSON FeatureCollection
            if 'features' in raw:
                df_limites = pd.json_normalize(raw['features'])
            else:
                df_limites = pd.json_normalize(raw)
            df_limites.dropna(how='all', inplace=True)
            con.register("df_limites", df_limites)
            con.execute("CREATE TABLE limites_alcaldias AS SELECT * FROM df_limites")
            print("Table 5: 'limites_alcaldias' CREATED")
        except Exception as e:
            print(f"Error loading 'limites_alcaldias': {e}")

        # Confirm row counts
        for table in ["crimes_clean", "lineas_metro", "alcaldias_cdmx", "estaciones_metro", "limites_alcaldias"]:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"- {table}: {count} filas")

        con.close()
        print("\nDone!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_database()