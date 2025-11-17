import streamlit as st
import pandas as pd
import numpy as np
import models.xgboost_plus_prophet as model
import altair as alt
from assets.css.theme import theme_css

# ===================== Model Prediction Page =====================

st.markdown(theme_css(), unsafe_allow_html=True)

st.set_page_config(layout="wide", page_title="Predicción de riesgo")

st.title("Predicción de riesgo delictivo por estación")
st.markdown("Usa esta herramienta para ver una predicción de riesgo para las próximas 4 semanas "
            "y analizar los patrones históricos de crimen alrededor de una estación de metro.")

@st.cache_data
def load_station_list():
    stations_df = model.get_available_stations()
    return stations_df

stations_df = load_station_list()

if stations_df.empty:
    st.error("No se pudieron cargar las estaciones desde la base de datos. "
             "Revisa la conexión y las tablas 'lines_metro' y 'daily_affluence'.")
    st.stop()

st.header("Configuración de Análisis")
    
stations_df['display_name'] = stations_df['nombre']
    
selected_station_display = st.selectbox(
    "Selecciona una Estación de Metro:",
    options=stations_df['display_name'],
    index=0
)
    
selected_station_row = stations_df[stations_df['display_name'] == selected_station_display].iloc[0]
selected_key = selected_station_row['key']
selected_name = selected_station_row['nombre']
    
radius_m = st.slider(
    "Radio de búsqueda (metros):",
    min_value=50,
    max_value=500,
    value=150,
    step=25,
    help="Define el área alrededor de la estación para buscar crímenes."
)
    
run_button = st.button("Generar Predicción", type="primary")


if run_button:  
    with st.spinner(f"Analizando '{selected_name}' (radio: {radius_m}m)... Esto puede tardar 1-2 minutos."):
        try:
            # Esta es la función principal del módulo
            results = model.run_full_prediction_pipeline(
                station_key_or_name=selected_key, # Usamos la 'key' para precisión
                radius_m=radius_m
            )
            st.session_state['prediction_results'] = results
            st.session_state['last_run_params'] = (selected_key, radius_m)
            st.success(f"Análisis completado para: {results['station_name']}")
            
        except Exception as e:
            st.session_state['prediction_results'] = None
            st.error(f"Error al generar la predicción: {e}")
            st.exception(e) # Imprime el stack trace completo para debug

if 'prediction_results' in st.session_state and st.session_state['prediction_results'] is not None:
    
    results = st.session_state['prediction_results']
    
    st.header(f"Resultados para: {results['station_name']}")
    
    tab1, tab2, tab3 = st.tabs(
        ["Predicción 4 Semanas", "Patrones de Crimen", "Datos Históricos"]
    )
    
    with tab1:
        st.subheader("Predicción de Riesgo Semanal (Próximas 4 Semanas)")
        
        pred_df = results['pred_enriched'].copy()
        
        pred_df['ds'] = pd.to_datetime(pred_df['ds']).dt.strftime('%Y-%m-%d')
        pred_df = pred_df.rename(columns={
            "ds": "Fecha de Predicción",
            "prob_semana_%": "Prob. de Evento (%)",
            "riesgo": "Nivel de Riesgo",
            "dia_probable": "Día Más Probable",
            "hora_rango_probable": "Hora Más Probable",
            "tipo_probable": "Tipo de Crimen Probable"
        })
        
        next_week = pred_df.iloc[0]
        st.markdown(f"**Semana del {pd.to_datetime(next_week['Fecha de Predicción']) - pd.Timedelta(days=6):%Y-%m-%d} al {next_week['Fecha de Predicción']}:**")
        
        cols_metric = st.columns(3)
        cols_metric[0].metric("Nivel de Riesgo", next_week['Nivel de Riesgo'])
        cols_metric[1].metric("Probabilidad de Evento", f"{next_week['Prob. de Evento (%)']:.1f}%")
        cols_metric[2].metric("Día Más Probable", next_week['Día Más Probable'])
        
        st.dataframe(
            pred_df[[
                "Fecha de Predicción", "Nivel de Riesgo", "Prob. de Evento (%)", 
                "Día Más Probable", "Hora Más Probable", "Tipo de Crimen Probable"
            ]],
            hide_index=True,
            use_container_width=True
        )
        
    with tab2:
        st.subheader(f"Patrones Históricos de Crimen (Radio de {results['radius']}m)")
        
        dow_df = results['prob_dow']
        hour_df = results['prob_hour']
        tipo_df = results['prob_tipo']
        
        if dow_df.empty and hour_df.empty and tipo_df.empty:
            st.warning("No se encontraron suficientes datos históricos de crímenes "
                       "en este radio para generar patrones detallados.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Probabilidad por Día de la Semana")
                if not dow_df.empty:
                    chart_dow = alt.Chart(dow_df).mark_bar().encode(
                        x=alt.X('dia', sort=dow_df['dow'].tolist(), title="Día"),
                        y=alt.Y('prob_%', title="Probabilidad (%)"),
                        tooltip=['dia', 'prob_%']
                    ).interactive()
                    st.altair_chart(chart_dow, use_container_width=True)
                else:
                    st.info("No hay datos de día de la semana.")
            
            with col2:
                st.markdown("##### Probabilidad por Hora del Día")
                if not hour_df.empty:
                    chart_hour = alt.Chart(hour_df).mark_bar().encode(
                        x=alt.X('hora', title="Hora (0-23)", axis=alt.Axis(format='d')),
                        y=alt.Y('prob_%', title="Probabilidad (%)"),
                        tooltip=['hora', 'prob_%']
                    ).interactive()
                    st.altair_chart(chart_hour, use_container_width=True)
                else:
                    st.info("No hay datos de hora del día.")
            
            st.markdown("##### Tipos de Crímenes Más Comunes")
            if not tipo_df.empty:
                st.dataframe(
                    tipo_df.rename(columns={"tipo": "Tipo de Crimen", "porcentaje": "Porcentaje (%)"}),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("No hay datos de tipo de crimen.")

    with tab3:
        st.subheader("Serie de Tiempo Diaria Usada para el Modelo")
        
        hist_df = results['daily_history']
        hist_df['ds'] = pd.to_datetime(hist_df['ds'])
        
        st.markdown("Esta es la serie de tiempo diaria que se construyó para la estación, "
                    "combinando la afluencia diaria y el conteo de robos encontrados dentro del radio.")

        # Gráfico de Afluencia y Robos
        base = alt.Chart(hist_df).encode(
            x=alt.X('ds', title="Fecha")
        )
        
        line_afluencia = base.mark_line(color='blue').encode(
            y=alt.Y('afluencia', title="Afluencia", axis=alt.Axis(titleColor='blue')),
            tooltip=['ds', 'afluencia']
        )
        
        line_robos = base.mark_line(color='red').encode(
            y=alt.Y('robos', title="Robos", axis=alt.Axis(titleColor='red')),
            tooltip=['ds', 'robos']
        )
        
        chart_hist = alt.layer(line_afluencia, line_robos).resolve_scale(
            y = 'independent'
        ).interactive()
        
        st.altair_chart(chart_hist, use_container_width=True)
        
        with st.expander("Ver datos históricos (tabla)"):
            st.dataframe(hist_df, use_container_width=True)

else:
    st.info("Selecciona una estación y haz clic en 'Generar Predicción' para comenzar el análisis.")