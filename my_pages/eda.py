import streamlit as st
from app.theme import theme_css
from utils.eda_plotting import plot_near_stations, plot_robbery_pie_chart, plot_crime_heatmap, plot_hourly_robberies

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

st.title("Exploración de Datos")

with st.expander("Introducción", expanded=False):
    st.markdown("""
                ### Introducción  
                México enfrenta actualmente una crisis de seguridad cada vez más compleja que afecta directamente la vida cotidiana y las actividades económicas. Según el INEGI, en marzo de 2024, el 61% de la población mayor de 18 años consideró inseguro vivir en su ciudad, mientras que más del 90% de los delitos denunciados permanecen sin resolver, lo que refuerza un clima de impunidad. En este panorama, los asaltos y robos destacan entre los delitos más frecuentes: en 2023, el fraude (6.9%), el robo o asalto en la calle y en el transporte público (6.5%), y la extorsión (5.2%) encabezaron la lista. La situación se agrava por condiciones socioeconómicas como la pobreza, el desempleo y la desigualdad, que aumentan la vulnerabilidad de los jóvenes y trabajadores urbanos.
                Un factor particularmente relevante hoy en día es la importancia de los dispositivos electrónicos. Los teléfonos inteligentes, laptops y tabletas ya no son artículos de lujo, sino herramientas indispensables tanto en el ámbito laboral como en la vida diaria. En 2024, México alcanzó 130 millones de líneas móviles activas, y el 97% de los usuarios de internet acceden a la red a través de un smartphone. Esta dependencia ha convertido a los dispositivos electrónicos en los principales objetivos de robo, ya que no solo tienen valor económico, sino también informativo. Su portabilidad, uso constante en espacios públicos y relevancia para la productividad empresarial amplifican el impacto social y económico del hurto.
                Además, la inseguridad en el transporte público genera una brecha de oportunidades particularmente crítica para los jóvenes. Muchos estudiantes y trabajadores dependen del metro y otros sistemas de transporte para cumplir con sus responsabilidades, pero la posibilidad de perder sus pertenencias electrónicas en un asalto aumenta la ansiedad y desalienta el uso del transporte público. Esto crea un círculo vicioso: cuanto mayor es la percepción de riesgo, más difícil se vuelve acceder a la educación y al empleo en condiciones seguras. En este sentido, el miedo no solo limita la movilidad, sino también el desarrollo académico y profesional de una generación que debería estar enfocada en construir su futuro.
    """, unsafe_allow_html=True)

with st.expander("Generación de Hipótesis", expanded=False):
    st.markdown("""
                ### Generación de Hipótesis  
                Con el apoyo de herramientas tecnológicas como el análisis de datos y la inteligencia artificial, este proyecto analiza información de la Fiscalía General de Justicia de la Ciudad de México (FGJ-CDMX) entre 2016 y 2025, con el objetivo de identificar patrones temporales y espaciales. Esto se basa en los factores legales, demográficos y socioeconómicos revisados. Este enfoque nos permite comprender cómo los factores estructurales, combinados con la movilidad y el valor de los dispositivos electrónicos, moldean los patrones delictivos en la ciudad.
    """, unsafe_allow_html=True)

st.markdown("""
<div style='text-align: center; padding: 1em;'>
    <h2 style='font-size: 32px; font-weight: bold; color: #d17c00;'>Hipótesis</h2>
    <p style='font-size: 20px; max-width: 800px; margin: auto;'>
        El riesgo de robo en la Ciudad de México aumenta en horarios clave de la jornada laboral 
        (6:00-8:00 a.m., 1:00-3:00 p.m. y 5:00-7:00 p.m.), particularmente los lunes y viernes —días tradicionales de pago conocidos como “quincenas”—, 
        y es significativamente mayor en zonas cercanas a estaciones del metro.
    </p>
</div>
""", unsafe_allow_html=True)

with st.expander("Metodología", expanded=False):
    st.markdown("""
                ### Metodología
                En esta fase cargamos el conjunto de datos original y estandarizamos todos los campos de fecha y hora mediante un análisis flexible para evitar errores críticos, además de eliminar duplicados y descartar registros con fechas futuras o información incompleta. Los campos categóricos clave, como tipo de delito, alcaldía y colonia, fueron normalizados eliminando acentos y convirtiéndolos a mayúsculas, mientras que los valores faltantes se imputaron como “DESCONOCIDO”. Las columnas de texto con valores numéricos se convirtieron a formato numérico y se generaron campos auxiliares como día de la semana y hora para facilitar el análisis. Este paso fue esencial para filtrar inconsistencias y preparar un conjunto de datos coherente para probar nuestras hipótesis.
    """, unsafe_allow_html=True)

st.markdown("""
<div style='text-align: left; padding: 1em;'>
    <h2 style='font-size: 32px; font-weight: bold;'>Hallazgos</h2>
    <p style='font-size: 16px; margin: auto;'>
        Se evaluó el riesgo de robo dentro de un radio de 50 metros de las estaciones de Metro comparando los delitos cercanos a las estaciones con el resto de la ciudad, ajustando por la superficie cubierta. El análisis calcula la proporción de área en buffer, la proporción de delitos y la razón de tasas de incidencia (IRR) con pruebas de significancia, además de una prueba binomial para detectar una sobrerrepresentación espacial.
    </p>
</div>
""", unsafe_allow_html=True)

plot_near_stations()

st.markdown("""
<div style='text-align: left; padding: 1em;'>
    <p style='font-size: 16px; margin: auto;'>
        A nivel de línea, los buffers de 50 m generan densidades de delito (delitos/km²), que se correlacionan con el tamaño de la red y el área mediante pruebas de Pearson/Spearman y regresiones lineales. Luego, gráficos de barras y archivos CSV permiten identificar qué líneas concentran el mayor riesgo, diferenciando los efectos de densidad del efecto de escala de la red.
        Usando otros datos combinados con los nuestros - ¿Qué obtenemos?
        Creamos manualmente una base de datos con las coordenadas de las estaciones del Metro, enfocándonos específicamente en las líneas 1 a la 11, utilizando como punto de partida datos GeoJSON incompletos. Esto nos permitió concentrarnos directamente en las estaciones para nuestra hipótesis, garantizando un análisis espacial preciso a pesar de las limitaciones del conjunto de datos original.
""", unsafe_allow_html=True)

plot_robbery_pie_chart()

st.markdown("""
------
**Mapa de calor: Todos los delitos por día y por hora**
**Qué muestra:** Un solo mapa de calor con el total de delitos por hora (0-23) y día (lunes-domingo).

**Puntos clave:**

* Actividad consistentemente baja entre las 00:00 y las 05:00.
* Se destacan las franjas de movilidad entre semana (mañana / comida / tarde).
* El viernes presenta la mayor intensidad combinada; el sábado mantiene niveles elevados al mediodía y por la tarde.

**Por qué importa:** Confirma la concentración temporal: los recursos deben asignarse según la demanda por día y hora, no únicamente por puntos geográficos calientes.

""")

plot_crime_heatmap()

st.markdown("""
------
**Robos por hora según el día**
**Qué muestra:** Perfiles de robos (solo robos) por hora, con una línea por cada día de la semana.
**Puntos clave:**
* Todos los días comparten picos alrededor del mediodía y la tarde; los viernes y sábados son consistentemente más altos en esas franjas.
* El domingo muestra menor actividad en la mañana, con un aumento moderado por la tarde.
**Por qué importa:** El riesgo de robo sigue un ritmo predecible; los despliegues operativos y las alertas al público pueden programarse estratégicamente (por ejemplo, alrededor de la hora de comida y la tarde en viernes y sábado).

""")

plot_hourly_robberies()

with st.expander("Conclusión", expanded=False):
    st.markdown("""
                ## Discusión

                **El objetivo de esta investigación** fue evaluar la hipótesis de que, en la Ciudad de México, el riesgo de robo aumenta durante horas clave de los días laborales —de **6:00 a 8:00 a.m.**, **1:00 a 3:00 p.m.** y **5:00 a 7:00 p.m.**—, especialmente los lunes y viernes, considerando las fechas tradicionales de pago (*“quincenas”*), y que este riesgo es significativamente mayor cerca de las estaciones del Metro, reflejando un vínculo entre la **proximidad al transporte** y los **patrones temporales del delito**. El objetivo final es garantizar que la población pueda realizar sus actividades académicas y profesionales de manera segura.

                ---
                #### **Buenas noticias**

                Los resultados **confirman parcialmente** la hipótesis. Los mapas de calor y mapas dinámicos muestran que los horarios de la mañana y la tarde **concentran el mayor número de robos**, particularmente los *lunes* y *viernes*, lo que respalda la relación entre el flujo de personas y la incidencia delictiva. La comparación entre escenarios revela un **aumento del 7.7%** en incidentes críticos durante estos periodos y picos, confirmando la influencia de la **proximidad a las estaciones del Metro**.
                
                ---
                
                #### **Malas noticias**

                Sin embargo, la **tercera variable temporal**, el *“día de pago”*, **no se confirma**. Ni los gráficos de líneas ni los análisis de regresión lineal muestran evidencia de que los días de quincena tengan una mayor incidencia de robos. Los datos indican que en esos días los robos se encuentran en el rango inferior, mientras que los picos más altos se registran en otros días, como el 2, 8, 10, entre otros. Los **bajos valores de R² en las regresiones (0.030 y 0.014)** confirman que la variación en el tipo de delito **no puede explicarse linealmente** por las fechas tradicionales de pago en México.
                
                ---
                
                ## Consideraciones finales

                El **flujo de pasajeros**, también conocido como *“afluencia”*, fue una de nuestras variables clave, pero los registros oficiales disponibles en los portales del gobierno solo incluían datos de tráfico de las líneas 1 a la 11 del Metro entre **2000 y 2012**, según el archivo CSV de líneas del Metro. La línea 12 carecía de información histórica, por lo que recopilamos manualmente sus coordenadas para completar el análisis. Estas discrepancias y la **falta de datos uniformes** representan la mayor limitación al intentar incorporar otras variables relacionadas con la movilidad y la densidad de pasajeros en la investigación.

                ### **Consideraciones finales - por todos los integrantes del equipo**

                **¿Qué aprendimos de los datos y qué sería interesante explorar más adelante? ¿Cómo responde esto a la hipótesis analítica?**
                A través del *Análisis Exploratorio de Datos (EDA)* y del estudio de los robos en la Ciudad de México, aprendimos que **no siempre es necesario usar toda la información disponible**. Es más eficiente enfocarse en **variables clave**, pero sin perder de vista el **contexto general** de los datos, de modo que las decisiones analíticas sean informadas y fundamentadas. Asimismo, **explorar nuevas librerías o herramientas**, más allá de las ya conocidas, amplía nuestras capacidades analíticas y permite refinar los resultados obtenidos.
                
                ---
                
                ### **Oportunidades interesantes para profundizar**

                A pesar de las limitaciones mencionadas —como la falta de datos completos sobre la afluencia en la línea 12 del Metro o la variabilidad de los horarios laborales—, es posible apoyarse en los **portales y foros de datos abiertos del gobierno**. Sin embargo, siempre será esencial **verificar y validar la confiabilidad de la información** antes de integrarla al análisis.
                
                ---
                
                #### **Densidad poblacional**
                Incorporar datos sobre la densidad de población podría mejorar significativamente la investigación, ya que permitiría correlacionar las áreas con mayor concentración de personas con la ocurrencia de robos. Esto ayudaría a determinar si ciertos patrones delictivos son consecuencia directa de la **densidad de usuarios en las estaciones** y no solo del horario o la cercanía al Metro.
                
                ---
                
                #### **Iluminación e inversión urbana**

                La **iluminación pública** y los **recursos asignados a cada alcaldía o municipio** también son factores críticos. Una menor inversión en infraestructura de seguridad urbana podría estar asociada con una mayor incidencia de robos, mientras que la presencia de **postes con cámaras del C5** podría incrementar la probabilidad de detección del delito. Incorporar estos indicadores en futuros análisis permitiría **reforzar la relación entre infraestructura urbana y criminalidad**, ayudando a validar o complementar la hipótesis inicial.
                
                ---
                
                #### **Afluencia o datos de tráfico**
                Si en futuras investigaciones se lograra obtener **datos completos de afluencia para todas las líneas del Metro**, sería posible calcular **tasas de delito por pasajero**, en lugar de solo conteos absolutos. Esto permitiría un análisis **más realista y preciso** sobre la correlación entre el flujo de personas y el riesgo de robo, aportando una perspectiva más sólida para la toma de decisiones en materia de seguridad y movilidad.
    """, unsafe_allow_html=True)