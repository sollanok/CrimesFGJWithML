import streamlit as st
from app.theme import theme_css
import socket

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

st.title("Chat con experto en los datos")

# CAN ONLY WORK LOCALLY!!!
def is_localhost():
    hostname = socket.gethostname()
    local_ips = ["localhost", "127.0.0.1"]
    try:
        ip = socket.gethostbyname(hostname)
        return ip.startswith("127.") or ip == "localhost"
    except:
        return False

if not is_localhost():
    st.error("""
    **Este chatbot solo funciona en ejecución local.**

    Por razones de seguridad, el acceso al chatbot está restringido cuando se abre desde el enlace de Streamlit Cloud u otros entornos públicos.

    Esto protege tu sistema contra:
    - Exposición de credenciales o claves API
    - Acceso no autorizado a flujos de automatización (n8n)
    - Riesgos de ejecución remota o manipulación de datos sensibles

    Ejecuta la app localmente para habilitar el chatbot.
    """)
    st.stop()
