import streamlit as st
import base64
from assets.css.theme import theme_css

# Inject theme
st.markdown(theme_css(), unsafe_allow_html=True)

if "role" not in st.session_state:
    st.session_state.role = None

def login():
    # Background image logic
    def encode_image(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    bright_img = encode_image("assets/images/landing-bright.png")
    dark_img = encode_image("assets/images/landing-dark.png")
    st.markdown(f"""
        <style>
        @media (prefers-color-scheme: light) {{
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/png;base64,{bright_img}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}
        }}
        @media (prefers-color-scheme: dark) {{
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/png;base64,{dark_img}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}
        }}
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='font-size: 64px; margin-bottom: 0;'>Bienvenido</h1>
            <p style='font-size: 28px; margin-top: 8px;'>Escoge qué rol es el que mejor te describe:</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        selected_role = st.segmented_control(
            label="",
            options=["Soy policía", "Soy de Thales"],
            selection_mode="single",
            label_visibility="collapsed",
            width=150
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Entrar") and selected_role:
            st.session_state.role = selected_role
            st.rerun()



def logout():
    st.markdown("""
                <div style='text-align: left;'>
                <p style='font-size: 28px; margin-top: 8px;'>Salir de la sesión</p>
                </div>
                """, unsafe_allow_html=True)

    if st.button("Salir"):
        st.session_state.role = None
        st.rerun()

role = st.session_state.role
logout_page = st.Page(logout, title="Salir de sesión", icon=":material/logout:")

visualization = st.Page(
    "my_pages/visualization.py",
    title="Visualización",
    icon=":material/dashboard:",
)

eda = st.Page(
    "my_pages/eda.py",
    title="Exploración Analítica",
    icon=":material/search:",
)

prediction = st.Page(
    "my_pages/prediction.py",
    title="Predicción con ML",
    icon=":material/science:",
)

chatbot = st.Page(
    "my_pages/chatbot.py",
    title="Chatbot",
    icon=":material/chat:",
)

account_page = [logout_page]
visualization_page = [visualization]
ml_page = [prediction]
eda_page = [eda]
chat_page = [chatbot]

page_dict = {}

if st.session_state.role in ["Soy de Thales", "Soy policía"]:
    page_dict["Visualización"] = visualization_page
if st.session_state.role in ["Soy de Thales", "Soy policía"]:
    page_dict["Exploración Analítica"] = eda_page
if st.session_state.role == "Soy de Thales":
    page_dict["Predicción con ML"] = ml_page
if st.session_state.role in ["Soy de Thales"]:
    page_dict["Chatbot"] = chat_page

if len(page_dict) > 0:
    pg = st.navigation({"Cuenta": account_page} | page_dict)
else:
    pg = st.navigation([st.Page(login)])

pg.run()