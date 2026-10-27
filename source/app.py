import streamlit as st

from grafo.grafo_principal import crear_estado_inicial, crear_grafo

NOMBRE_VISIBLE_DE_AGENTE = {"buscador": "Buscador", "linaje": "Linaje", "detalle": "Detalle"}

st.set_page_config(page_title="Data Discovery AI", page_icon="📊")
st.title("Data Discovery AI")
st.caption("Preguntame en que dashboard basarte, que vistas o tablas usar, de donde salen los datos "
           "o que significa una columna.")


@st.cache_resource
def obtener_grafo():
    return crear_grafo()


if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for rol, texto in st.session_state.mensajes:
    with st.chat_message("user" if rol == "usuario" else "assistant"):
        st.markdown(texto)

pregunta = st.chat_input("Escribe tu pregunta")
if pregunta:
    st.session_state.mensajes.append(("usuario", pregunta))
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        respuesta_final = ""
        # Muestra en vivo que agente trabaja en cada paso
        with st.status("Pensando...", expanded=False) as estado_visual:
            entrada = crear_estado_inicial(list(st.session_state.mensajes))
            for actualizacion in obtener_grafo().stream(entrada, stream_mode="updates"):
                for nombre_nodo, cambios in actualizacion.items():
                    if nombre_nodo == "orquestador" and cambios["siguiente_agente"] != "responder":
                        nombre_agente = NOMBRE_VISIBLE_DE_AGENTE[cambios["siguiente_agente"]]
                        estado_visual.write(f"**{nombre_agente}**: {cambios['instruccion']}")
                    elif nombre_nodo == "redactor":
                        respuesta_final = cambios["respuesta_final"]
            estado_visual.update(label="Listo", state="complete")
        st.markdown(respuesta_final)
    st.session_state.mensajes.append(("asistente", respuesta_final))
