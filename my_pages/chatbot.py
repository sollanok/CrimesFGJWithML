import streamlit as st
from utils.chatbot_backend import get_routing_decision, get_sql_and_answer 

st.set_page_config(page_title="Chat con experto", layout="wide")
st.title("Chat con experto de crímenes en la CDMX y sus estaciones del metro")
st.markdown("Pregunta sobre tipos de delitos, ubicaciones o afluencia del metro.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! ¿Qué te gustaría analizar sobre los datos de crímenes hoy?"}
    ]

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Escribe tu pregunta aquí..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.pending_question:
        full_prompt = st.session_state.pending_question + " " + prompt
        
        st.session_state.pending_question = None 
        
        with st.chat_message("assistant"):
            with st.spinner("Analizando la información completa..."):
                response = get_sql_and_answer(full_prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    else:
        with st.spinner("Analizando pregunta..."):
            decision = get_routing_decision(prompt) 
            status = decision.get("status")
            response_text = decision.get("response")

        if status == "PROCEED":
            with st.chat_message("assistant"):
                with st.spinner("Generando SQL y consultando la base de datos..."):
                    response = get_sql_and_answer(prompt) 
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

        elif status == "CLARIFY":
            st.session_state.pending_question = prompt 
            
            with st.chat_message("assistant"):
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
        
        else:
             with st.chat_message("assistant"):
                error_msg = "Hubo un error al procesar el enrutador de detalles. Procediendo de todas formas..."
                st.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                with st.spinner("Consultando la base de datos..."):
                    response = get_sql_and_answer(prompt) 
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})