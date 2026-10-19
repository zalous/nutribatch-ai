import streamlit as st
from database import get_inventario


def render():
    st.header("🍳 Cocinar Hoy y Despensa")
    st.caption("Nevera, congelador, despensa y control de fechas de cocinado.")

    subtabs = st.tabs(
        ["🧊 Nevera & Congelador", "🥘 Tápers Batch", "📸 Foto Encimera", "🆘 Rescate"]
    )

    with subtabs[0]:
        st.subheader("Estado de la Despensa y Frescos")
        try:
            items_nevera = get_inventario("nevera")
            items_congelador = get_inventario("congelador")
            items_despensa = get_inventario("despensa")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nevera", f"{len(items_nevera)} ítems")
            with col2:
                st.metric("Congelador", f"{len(items_congelador)} ítems")
            with col3:
                st.metric("Despensa", f"{len(items_despensa)} ítems")

            if not (items_nevera or items_congelador or items_despensa):
                st.info("La despensa está vacía. Añadiremos alimentos en la Fase 2.")
        except Exception as e:
            st.error(f"Error al conectar con el inventario: {e}")

    with subtabs[1]:
        st.subheader("Tápers Cocinados y Antigüedad")
        st.info(
            "Aquí se mostrarán los tápers cocinados, qué día exacto se hicieron y cuántos días llevan en la nevera para garantizar máxima seguridad y frescura."
        )

    with subtabs[2]:
        st.subheader("Foto en Encimera")
        st.info(
            "En la Fase 4 podrás sacar una foto rápida a los ingredientes de la encimera para que la IA los reconozca y descuente del inventario."
        )

    with subtabs[3]:
        st.subheader("Recetas de Rescate (Miércoles / Jueves)")
        st.info(
            "La IA analizará lo que queda por gastar y los huecos de nutrientes de la semana para sugerirte la mejor comida de rescate."
        )
