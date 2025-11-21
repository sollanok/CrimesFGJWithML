import streamlit as st
import pandas as pd
import models.xgboost_plus_prophet as model
import plotly.graph_objects as go
import plotly.express as px
from assets.css.theme import theme_css
import time
from utils.map_visualization import plot_prediction_animated_map

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

st.header("Configuración de análisis")

stations_df['display_name'] = stations_df['nombre']
station_names = sorted(stations_df['nombre'].astype(str).unique())

selected_station_display = st.selectbox(
    "Selecciona una estación de metro:",
    options=station_names,
    index=None,
    placeholder="Ej. Chabacano"
)
if selected_station_display:
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
    
run_button = st.button("Generar predicción", type="primary")


if run_button:  
    with st.spinner(f"Analizando '{selected_name}' (radio: {radius_m}m)... Esto puede tardar 1-2 minutos."):
        try:
            results = model.run_full_prediction_pipeline(
                station_key_or_name=selected_key,
                radius_m=radius_m
            )
            st.session_state['prediction_results'] = results
            st.session_state['last_run_params'] = (selected_key, radius_m)
            st.success(f"Análisis completado para: {results['station_name']}")
            
        except Exception as e:
            st.session_state['prediction_results'] = None
            st.error(f"Error al generar la predicción: {e}")
            st.exception(e)

if 'prediction_results' in st.session_state and st.session_state['prediction_results'] is not None:
    
    results = st.session_state['prediction_results']
    
    st.header(f"Resultados para: {results['station_name']}")
    
    tab1, tab2, tab3 = st.tabs(
        ["Predicción semanal", "Patrones de crimen", "Datos históricos"]
    )
    
    with tab1:
        pred_df = results['pred_enriched'].copy()
        
        pred_df['ds'] = pd.to_datetime(pred_df['ds']).dt.strftime('%Y-%m-%d')
        pred_df = pred_df.rename(columns={
            "ds": "Semana termina el",
            "prob_semana_%": "Prob. de evento (%)",
            "riesgo": "Nivel de riesgo",
            "dia_probable": "Día más probable",
            "hora_rango_probable": "Hora más probable",
            "tipo_probable": "Tipo de crimen probable"
        })
        
        pred_df["Tipo de crimen probable"] = pred_df["Tipo de crimen probable"].str.capitalize()

        next_week = pred_df.iloc[0]
        st.subheader(f"Predicción de la **semana del {pd.to_datetime(next_week['Semana termina el']) - pd.Timedelta(days=6):%Y-%m-%d} al {next_week['Semana termina el']}:**")
        
        cols_metric = st.columns(4)
        cols_metric[0].metric("Nivel de riesgo", next_week['Nivel de riesgo'])
        cols_metric[1].metric("Probabilidad de evento", f"{next_week['Prob. de evento (%)']:.1f}%")
        cols_metric[2].metric("Día más probable", next_week['Día más probable'])
        crime_text = next_week['Tipo de crimen probable']
        cols_metric[3].markdown(
            f"""
            <div style="margin-bottom: 0px;">
                <p style="font-size: 14px; margin-bottom: 0px; color: #888;">Evento</p>
                <p style="font-size: 18px; font-weight: 600; line-height: 1.2; margin-top: 0px;">
                    {crime_text}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.subheader(f"Predicción de las próximas 4 semanas:")
        st.dataframe(
            pred_df[[
                "Semana termina el", "Nivel de riesgo", "Prob. de evento (%)", 
                "Día más probable", "Hora más probable", "Tipo de crimen probable"
            ]],
            hide_index=True,
            width='stretch'
            )
        st.subheader(f"Visualización animada:")
        
        lat = selected_station_row['lat']
        lon = selected_station_row['lon']

        min_global_prob = pred_df['Prob. de evento (%)'].min()
        max_global_prob = pred_df['Prob. de evento (%)'].max()

        col_map_controls = st.columns([3, 1])

        with col_map_controls[0]:
            week_index = st.slider(
                "Línea de tiempo de predicción:",
                min_value=0,
                max_value=len(pred_df) - 1,
                value=0,
                format="Semana +%d"
            )

        map_placeholder = st.empty()

        with col_map_controls[1]:
            if st.button("▶️ Animar", type="primary"):
                progress_bar = st.progress(0)
        
                for i in range(len(pred_df)):
                    row = pred_df.iloc[i]
            
                    deck_map = plot_prediction_animated_map(
                        station_lat=lat,
                        station_lon=lon,
                        station_name=selected_name,
                        prediction_row=row,
                        radius_m=radius_m
                    )
                    
                    map_placeholder.pydeck_chart(deck_map, height=500, key=f"anim_{i}")
                    progress_bar.progress((i + 1) / len(pred_df))
                    time.sleep(0.5)
            
                    map_placeholder.pydeck_chart(deck_map, height=500, key=f"anim_{i}")

                    progress_bar.progress((i + 1) / len(pred_df))
                    time.sleep(3)
                
                progress_bar.empty()

        current_row = pred_df.iloc[week_index]

        deck_map = plot_prediction_animated_map(
            station_lat=lat,
            station_lon=lon,
            station_name=selected_name,
            prediction_row=current_row,
            radius_m=radius_m,
        )

        st.caption(f"Mostrando semana: **{current_row['Semana termina el']}** | Riesgo: **{current_row['Prob. de evento (%)']:.1f}%**")
        
        # Render to the SAME placeholder used by the animation
        map_placeholder.pydeck_chart(deck_map, height=500)        
    with tab2:
        st.subheader(f"Análisis de patrones históricos de crimen (radio de {results['radius']}m)")
        
        dow_df = results['prob_dow']
        hour_df = results['prob_hour']
        tipo_df = results['prob_tipo']
        
        if dow_df.empty and hour_df.empty and tipo_df.empty:
            st.warning("No se encontraron suficientes datos históricos de crímenes "
                       "en este radio para generar patrones detallados.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Probabilidad por día de la semana")
    
                if not dow_df.empty:
                    day_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
                    dow_df_sorted = dow_df.sort_values(by='dow')

                    fig_dow = px.bar(
                        dow_df_sorted,
                        x='dia',
                        y='prob_%',
                        labels={'dia': 'Día', 'prob_%': 'Probabilidad (%)'},
                        title='Probabilidad histórica de eventos por día',
                        category_orders={"dia": day_order},
                        height=350 
                    )
        
                    fig_dow.update_layout(xaxis_title="Día",
                                          yaxis_title="Probabilidad (%)",
                                          paper_bgcolor='rgba(0,0,0,0)',
                                           plot_bgcolor='rgba(0,0,0,0)'
                    )
                    fig_dow.update_traces(marker_color='#E7BB67')

                    st.plotly_chart(fig_dow, width='stretch')
                else:
                    st.info("No hay datos de día de la semana.")

            with col2:
                st.markdown("##### Probabilidad por hora del día")
    
                if not hour_df.empty:
                    fig_hour = px.bar(
                        hour_df,
                        x='hora',
                        y='prob_%',
                        labels={'hora': 'Hora (0-23)', 'prob_%': 'Probabilidad (%)'},
                        title='Probabilidad histórica de eventos por hora',
                        height=350
                    )
        
                    fig_hour.update_layout(xaxis_title="Hora (0-23)",
                                           yaxis_title="Probabilidad (%)",
                                           paper_bgcolor='rgba(0,0,0,0)',
                                           plot_bgcolor='rgba(0,0,0,0)'
                    )

                    fig_hour.update_xaxes(dtick=1)
                    fig_hour.update_traces(marker_color='#9F2241')

                    st.plotly_chart(fig_hour, width='stretch')
                else:
                    st.info("No hay datos de hora del día.")
            
            st.markdown("##### Tipos de crímenes más comunes")
            if not tipo_df.empty:
                tipo_df["tipo"] = tipo_df["tipo"].str.capitalize()
                st.dataframe(
                    tipo_df.rename(columns={"tipo": "Tipo de crimen", "porcentaje": "Porcentaje (%)"}),
                    hide_index=True,
                    width='stretch'
                )
            else:
                st.info("No hay datos de tipo de crimen.")

    with tab3:
        st.subheader("Serie de tiempo diaria usada para el modelo")
        
        hist_df = results['daily_history']
        hist_df['ds'] = pd.to_datetime(hist_df['ds'])
        
        st.markdown("Esta es la serie de tiempo diaria que se construyó para la estación, "
                    "combinando la afluencia diaria y el conteo de robos encontrados dentro del radio.")

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=hist_df['ds'],
                y=hist_df['afluencia'],
                name='Afluencia',
                mode='lines',
                line=dict(color='#9F2241')
            )
        )

        fig.add_trace(
            go.Scatter(
                x=hist_df['ds'],
                y=hist_df['robos'],
                name='Robos',
                mode='lines',
                line=dict(color='#E7BB67'),
                yaxis='y2'
            )
        )

        fig.update_layout(
            title='Historial de afluencia vs. robos',
            xaxis_title='Año',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',

            yaxis=dict(
                title='Afluencia',
                title_font=dict(color='#9F2241'), 
                tickfont=dict(color='#9F2241')
            ),
    
            yaxis2=dict(
                title='Robos',
                title_font=dict(color='#E7BB67'),
                tickfont=dict(color='#E7BB67'),
                overlaying='y',
                side='right'
            ),
    
            hovermode="x unified",
            legend=dict(x=0, y=1.1, orientation="h")
        )

        st.plotly_chart(fig, width='stretch')
        
        with st.expander("Ver datos históricos (tabla)"):
            hist_df = hist_df.rename(columns={
                "ds": "Fecha",
                "afluencia": "Afluencia diaria",
                "robos": "Total eventos/robos",
                "aflu_ma7": "Afluencia prom. 7 días",
                "aflu_ma14": "Afluencia prom. 14 días",
                "ratio": "Ratio eventos/afluencia",
                "dow": "Día semana num.",
                "month": "Mes",
                "weekofyear": "Semana del año",
                "is_quincena": "¿Es quincena?",
                "is_weekend": "¿Es fin de semana?",
                "feriado": "¿Es feriado?"
            })
            st.dataframe(hist_df, width='stretch')

else:
    st.info("Selecciona una estación y haz clic en 'Generar predicción' para comenzar el análisis.")