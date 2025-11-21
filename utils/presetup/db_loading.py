# !! This is NOT meant to run as a module.
# This was executed manually as an app setup.
import duckdb
import pandas as pd
import os
import json

from unidecode import unidecode

# Base path to the root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Path to the 'data' folder
DATA_DIR = os.path.join(BASE_DIR, "data")

# File paths
DB_FILE = os.path.join(DATA_DIR, "crimes_FGJ.db")
CRIME_CSV = os.path.join(DATA_DIR, "carpetasFGJ_acumulado_2025_01.csv")
BOROUGH_JSON = os.path.join(DATA_DIR, "limite-de-las-alcaldas.json")
METRO_CSV = os.path.join(DATA_DIR, "lineas_metro.csv")
AFFLUENCE_CSV = os.path.join(DATA_DIR, "affluence_with_num_key.csv")

# ----------------------------
# ---- Cleaning Functions ----
# ----------------------------
def read_csv_utf8_fallback(path):
    try:
        return pd.read_csv(path, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding='latin1')

def load_data():
    try:
        df = pd.read_csv(CRIME_CSV, encoding='latin1', low_memory=False)
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
            df_lines = read_csv_utf8_fallback(METRO_CSV)
            df_lines.dropna(how='all', inplace=True)
            df_lines = df_lines[df_lines.apply(lambda row: row.count() > 1, axis=1)]
            con.register("df_lines", df_lines)
            con.execute("CREATE TABLE lines_metro AS SELECT * FROM df_lines")
            print("Table 2: 'lines_metro' CREATED")
        except Exception as e:
            print(f"Error loading 'lines_metro': {e}")
            
        # Borough limits JSON
        try:
            with open(BOROUGH_JSON, encoding='utf-8') as f:
                raw = json.load(f)
            # If it's a GeoJSON FeatureCollection
            if 'features' in raw:
                df_limites = pd.json_normalize(raw['features'])
            else:
                df_limites = pd.json_normalize(raw)
            df_limites.dropna(how='all', inplace=True)
            con.register("df_limites", df_limites)
            con.execute("CREATE TABLE borough_limits AS SELECT * FROM df_limites")
            print("Table 3: 'borough_limits' CREATED")
        except Exception as e:
            print(f"Error loading 'borough_limits': {e}")
        
        # Daily Affluence CSV
        try:
            df_affluence = pd.read_csv(AFFLUENCE_CSV, encoding='latin1')
            df_affluence.dropna(how='all', inplace=True)
            df_affluence = df_affluence[df_affluence.apply(lambda row: row.count() > 1, axis=1)]
            con.register("df_affluence", df_affluence)
            con.execute("CREATE TABLE daily_affluence AS SELECT * FROM df_affluence")
            print("Table 4: 'daily_affluence' CREATED")
        except Exception as e:
            print(f"Error loading 'daily_affluence': {e}")

        # Confirm row counts
        for table in ["crimes_clean", "lines_metro", "borough_limits", "daily_affluence"]:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"- {table}: {count} rows")

        con.close()
        print("\nDone!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_database()