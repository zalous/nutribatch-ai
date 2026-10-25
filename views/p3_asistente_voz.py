import streamlit as st

import ai_engine


def _mostrar_error(exc: Exception) -> None:
    st.error("No se pudo completar la consulta contextual.")
    with st.expander("Detalle técnico"):
        st.code(str(exc)[:600], language=None)


def render():
    st.header("🎙️ Asistente por Voz y Memoria")
    st.caption("Pregunta a la IA sobre tus comidas, fechas de cocinado o el menú del día.")

    st.info(
        "Prueba del motor contextual (Paso 3.1): consulta de solo lectura. "
        "El micrófono y las acciones sobre la base de datos llegarán en la Fase 4."
    )

    motor_listo = ai_engine.motor_contextual_disponible()
    if not motor_listo:
        st.warning(
            "Falta la GEMINI_API_KEY o el perfil clínico no está accesible. "
            "El motor contextual no puede responder todavía."
        )

    if "chat_contextual" not in st.session_state:
        st.session_state["chat_contextual"] = []

    for turno in st.session_state["chat_contextual"]:
        with st.chat_message(turno["role"]):
            st.markdown(turno["content"])

    with st.form("consulta_contextual", clear_on_submit=True):
        pregunta = st.text_input(
            "Consulta rápida por texto:",
            placeholder="Ej. ¿Qué día cocinamos el pollo? o ¿Qué ceno hoy antirreflujo?",
        )
        enviada = st.form_submit_button("Enviar consulta")

    if enviada:
        texto_pregunta = (pregunta or "").strip()
        if not texto_pregunta:
            st.warning("Escribe una consulta antes de enviarla.")
        elif not motor_listo:
            st.error("Configura GEMINI_API_KEY para usar el motor contextual.")
        else:
            with st.spinner("Consultando la despensa y el perfil clínico..."):
                try:
                    contexto = ai_engine.construir_contexto_vivo()
                    respuesta = ai_engine.consultar_asistente(
                        texto_pregunta,
                        historial_conversacion=st.session_state["chat_contextual"],
                        contexto=contexto,
                    )
                except Exception as exc:
                    _mostrar_error(exc)
                else:
                    st.session_state["chat_contextual"].append(
                        {"role": "user", "content": texto_pregunta}
                    )
                    st.session_state["chat_contextual"].append(
                        {"role": "assistant", "content": respuesta}
                    )
                    st.session_state["_ultimo_contexto_motor"] = contexto["texto"]
                    st.rerun()

    if st.session_state["chat_contextual"]:
        if st.button("Borrar conversación"):
            st.session_state["chat_contextual"] = []
            st.session_state.pop("_ultimo_contexto_motor", None)
            st.rerun()

    if st.session_state.get("_ultimo_contexto_motor"):
        with st.expander("Ver contexto vivo enviado a la IA"):
            st.code(st.session_state["_ultimo_contexto_motor"], language=None)
