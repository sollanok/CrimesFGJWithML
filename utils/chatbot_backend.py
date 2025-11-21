import json
import os
import duckdb
from google import genai
import streamlit as st

try:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("No API Key. Try again.")
    st.stop()

client = genai.Client()

DATABASE_PATH = "data/crimes_FGJ.db" 

DETAILS_EXPERT_PROMPT = """
Eres un analizador de preguntas. Tu objetivo es determinar si la pregunta del usuario es lo suficientemente específica para escribir una consulta SQL sobre una base de datos de crímenes.

Una pregunta **específica** tiene al menos uno de:
1. Un tipo de delito (ej. 'robo', 'homicidio').
2. Una ubicación (ej. 'alcaldia Cuauhtémoc', 'cerca del metro Zócalo', 'colonia Roma').
3. Una fecha o rango de fechas (ej. 'en 2023', 'el mes pasado', 'en enero').

Una pregunta **vaga** es general (ej. '¿Qué me puedes decir?', '¿Cómo está el crimen?', '¿Cuál es el peor delito?').

Responde ÚNICAMENTE con un objeto JSON con dos claves:
1. "status": debe ser "PROCEED" (si es específica) o "CLARIFY" (si es vaga).
2. "response": Si es "PROCEED", deja esto como una cadena vacía. Si es "CLARIFY", escribe una pregunta amigable para pedir los detalles que faltan (ej. '¡Claro! ¿Sobre qué tipo de delito o en qué alcaldía te gustaría saber?').
"""

SQL_EXPERT_PROMPT = """
Eres un experto de SQL. Necesitas generar una sola consulta en DuckDB basada en la pregunta del usuario. La consulta puede usar datos de las tablas:
1. 'crimes_clean': tiene datos de carpetas de investigación de 2016 a 2024. Columnas: 'anio_hecho', 'mes_hecho', 'fecha_hecho', 'hora_hecho', 'delito', 'colonia_hecho', 'alcaldia_hecho', 'longitud', 'latitud'.
2. 'lines_metro': tiene estaciones del metro. Columnas: 'num' (ID único), 'linea', 'nombre' (estación), 'lat', 'lon'.
3. 'daily_affluence': tiene afluencia diaria del metro. Columnas: 'key' (ID único, igual a 'num'), 'fecha', 'afluencia'.

Si el usuario quiere relacionar crímenes con estaciones del metro, usa ST_Distance_Sphere(ST_Point(lon1, lat1), ST_Point(lon2, lat2)) <= radio_en_metros.
NO incluyas explicaciones, markdown o cualquier otro texto extra; SOLO contesta con la consulta SQL.
"""

TEXT_EXPERT_PROMPT = """
Eres un amigable asistente AI especializado en datos de crímenes en la CDMX. Resume el JSON que se provee a una respuesta concisa que le ayude al usuario. NO menciones SQL o JSON.
"""

def get_routing_decision(user_message: str) -> dict:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[user_message],
            config={"system_instruction": DETAILS_EXPERT_PROMPT}
        )
        
        clean_response = response.text.strip().replace('`', '')
        if clean_response.startswith("json"):
            clean_response = clean_response[4:]
            
        decision = json.loads(clean_response)
        return decision

    except Exception as e:
        print(f"Error en el enrutador de detalles: {e}")
        # Si el enrutador falla, simplemente procede por seguridad
        return {"status": "PROCEED", "response": ""}

def get_sql_and_answer(full_user_message: str) -> str:
    try:
        response_sql = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[full_user_message],
            config={"system_instruction": SQL_EXPERT_PROMPT}
        )
        sql_query = response_sql.text.strip().replace('`', '').replace(';', '')
        
        if sql_query.lower().startswith("sql"):
            sql_query = sql_query[3:].strip()

        if not sql_query.lower().startswith('select'):
             return f"No pude generar una consulta SELECT válida para eso. (Consulta generada: {sql_query})"

    except Exception as e:
        return f"Error de AI (Generación de SQL): {e}"

    try:
        conn = duckdb.connect(database=DATABASE_PATH) 
        
        conn.execute("INSTALL spatial")
        conn.execute("LOAD spatial")

        result_df = conn.execute(sql_query).fetchdf()
        
        if result_df.empty:
            conn.close()
            return "No encontré resultados para esa consulta específica."

        json_data_string = result_df.to_json(orient='records')
        conn.close()
        
    except Exception as e:
        return f"Error de Base de Datos: La consulta falló. Consulta: {sql_query}. Error: {e}"
    
    try:
        full_prompt = f"Original question: {full_user_message}. Raw data result: {json_data_string}"
        
        response_text = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[full_prompt],
            config={"system_instruction": TEXT_EXPERT_PROMPT}
        )
        
        return response_text.text.strip()

    except Exception as e:
        return f"Error de AI (Generación de Texto): {e}"