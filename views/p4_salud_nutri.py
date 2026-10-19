import streamlit as st


def render():
    st.header("📊 Cuadro Clínico y Nutricional")
    st.caption("Seguimiento individual para Gonzalo y Marta según sus analíticas.")

    tab_gonzalo, tab_marta = st.tabs(["👨 Gonzalo (1.700 kcal)", "👩 Marta (1.350 kcal)"])

    with tab_gonzalo:
        st.subheader("Objetivos de Gonzalo")
        col1, col2, col3 = st.columns(3)
        col1.metric("Calorías", "0 / 1.700 kcal")
        col2.metric("Proteína", "0 / 155 g")
        col3.metric("Fibra", "0 / 35 g")

        st.markdown(
            """
        - **Colesterol LDL:** Prioridad fibra soluble y grasas mono/poliinsaturadas. Saturadas < 13 g/día.
        - **Ácido Úrico:** Control estricto de purinas.
        - **Vitamina D:** Suplementación y aporte semanal de pescado azul / huevos.
        """
        )

    with tab_marta:
        st.subheader("Objetivos de Marta")
        col1, col2, col3 = st.columns(3)
        col1.metric("Calorías", "0 / 1.350 kcal")
        col2.metric("Proteína", "0 / 115 g")
        col3.metric("Hierro", "0 / 20 mg")

        st.markdown(
            """
        - **Hierro y Ferropenia:** Prioridad hierro biodisponible + Vitamina C (evitar lácteos en la misma comida).
        - **Reflujo (ERG):** Cenas suaves, bajo contenido graso denso y cocciones limpias.
        - **Vitamina D:** Objetivo semanal sinérgico con Vitamina K.
        """
        )
