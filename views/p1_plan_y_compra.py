import streamlit as st
from database import get_lista_compra, add_item_lista_compra


def render():
    st.header("🛒 Planificación y Lista de la Compra")
    st.caption("Segundo cerebro unificado para comida, hogar y compras del súper.")

    tab_lista, tab_plan, tab_ticket = st.tabs(
        ["📝 Lista de la Compra", "📅 Plan Semanal", "🧾 Subir Ticket"]
    )

    with tab_lista:
        st.subheader("Añadir a la lista")
        with st.form("form_nuevo_item", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                item_nombre = st.text_input(
                    "Producto o ingrediente",
                    placeholder="Ej. Yogur griego ligero, papel cocina...",
                )
            with col2:
                categoria = st.selectbox(
                    "Categoría",
                    ["frescos", "despensa", "congelados", "hogar_y_otros"],
                )
            submitted = st.form_submit_button("➕ Añadir a la lista")
            if submitted and item_nombre.strip():
                add_item_lista_compra(
                    {
                        "item": item_nombre.strip(),
                        "categoria": categoria,
                        "origen": "manual_o_voz",
                        "comprado": False,
                    }
                )
                st.success(f"'{item_nombre}' añadido.")
                st.rerun()

        st.divider()
        st.subheader("Pendientes de comprar")
        try:
            pendientes = get_lista_compra(comprado=False)
            if pendientes:
                for item in pendientes:
                    st.checkbox(f"**{item['item']}** ({item['categoria']})", key=f"item_{item['id']}")
            else:
                st.info("No hay ítems pendientes en la lista de la compra.")
        except Exception as e:
            st.error(f"Error al cargar la lista: {e}")

    with tab_plan:
        st.subheader("Planificador Batch Cooking")
        st.info(
            "En la Fase 3, aquí podrás generar planes semanales automáticos con la IA que cuadren las 1.700 kcal de Gonzalo y las 1.350 kcal de Marta."
        )

    with tab_ticket:
        st.subheader("Lector de Tickets con IA")
        st.info(
            "En el Paso 2.2 podrás subir fotos o PDFs de tickets (Mercadona, Lidl, Consum...) para tachar de la lista y actualizar la despensa automáticamente."
        )
