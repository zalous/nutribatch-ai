import streamlit as st


def render():
    st.header("🎙️ Asistente por Voz y Memoria")
    st.caption("Pregunta a la IA sobre tus comidas, fechas de cocinado o añade a la compra.")

    st.info(
        "El asistente de voz se conectará con Gemini 2.5 Flash y el Perfil Clínico en la Fase 3 y 4."
    )

    audio_prompt = st.text_input(
        "Consulta rápida por texto o prueba tu pregunta:",
        placeholder="Ej. ¿Qué día cocinamos el pollo? o Apunta café a la compra...",
    )

    if st.button("Enviar consulta") and audio_prompt:
        st.write(f"Has preguntado: *{audio_prompt}*")
        st.success(
            "El motor de IA procesará esta consulta con el contexto completo de tu nevera y perfil clínico en la Fase 4."
        )
