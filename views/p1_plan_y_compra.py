from datetime import date
import streamlit as st
from database import (
    get_lista_compra,
    add_item_lista_compra,
    marcar_item_lista_compra,
    delete_item_lista_compra,
    procesar_y_guardar_ticket_items,
    get_diccionario_tickets,
)
from ai_engine import procesar_ticket_con_ia


def render():
    st.header("🛒 Planificación y Lista de la Compra")
    st.caption("Segundo cerebro unificado para comida, hogar y compras del súper.")

    tab_lista, tab_ticket, tab_plan, tab_dicc = st.tabs(
        ["📝 Lista de la Compra", "🧾 Subir Ticket (IA)", "📅 Plan Semanal", "📖 Memoria Tickets"]
    )

    # -------------------------------------------------------------------------
    # TAB 1: LISTA DE LA COMPRA
    # -------------------------------------------------------------------------
    with tab_lista:
        st.subheader("Añadir a la lista")
        with st.form("form_nuevo_item", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                item_nombre = st.text_input(
                    "Producto o ingrediente",
                    placeholder="Ej. Yogur griego ligero, bolsas de basura...",
                )
            with col2:
                categoria = st.selectbox(
                    "Categoría",
                    ["frescos", "despensa", "congelados", "hogar_y_otros"],
                    format_func=lambda x: {
                        "frescos": "🥦 Frescos / Nevera",
                        "despensa": "🥫 Despensa Seca",
                        "congelados": "❄️ Congelados",
                        "hogar_y_otros": "🧼 Hogar y Limpieza",
                    }[x],
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
                st.toast(f"'{item_nombre}' añadido a la lista.")
                st.rerun()

        st.divider()

        # Visualización de la lista clasificada por pasillos
        col_pend, col_comp = st.columns(2)

        with col_pend:
            st.subheader("🛒 Por Comprar")
            try:
                pendientes = get_lista_compra(comprado=False)
                if pendientes:
                    for item in pendientes:
                        c_check, c_del = st.columns([4, 1])
                        with c_check:
                            if st.button(
                                f"⚪ {item['item']} ({item['categoria']})",
                                key=f"check_{item['id']}",
                                help="Haz clic para marcar como comprado",
                            ):
                                marcar_item_lista_compra(item["id"], comprado=True)
                                st.rerun()
                        with c_del:
                            if st.button("❌", key=f"del_lc_{item['id']}"):
                                delete_item_lista_compra(item["id"])
                                st.rerun()
                else:
                    st.info("¡Lista vacía! No hay compras pendientes.")
            except Exception as e:
                st.error(f"Error al cargar lista: {e}")

        with col_comp:
            st.subheader("✅ Ya Comprados")
            try:
                comprados = get_lista_compra(comprado=True)
                if comprados:
                    for item in comprados:
                        c_check, c_del = st.columns([4, 1])
                        with c_check:
                            if st.button(
                                f"✔️ ~~{item['item']}~~",
                                key=f"uncheck_{item['id']}",
                                help="Haz clic para devolver a pendientes",
                            ):
                                marcar_item_lista_compra(item["id"], comprado=False)
                                st.rerun()
                        with c_del:
                            if st.button("❌", key=f"del_comp_{item['id']}"):
                                delete_item_lista_compra(item["id"])
                                st.rerun()
                else:
                    st.caption("Aún no has marcado productos como comprados.")
            except Exception as e:
                st.error(f"Error al cargar comprados: {e}")

    # -------------------------------------------------------------------------
    # TAB 2: LECTOR IA DE TICKETS
    # -------------------------------------------------------------------------
    with tab_ticket:
        st.subheader("🧾 Lector Inteligente de Tickets")
        st.caption(
            "Sube una foto, PDF o pega el texto del ticket de Mercadona, Lidl, Consum o Dia. "
            "La IA separará la comida del hogar, guardará en despensa y tachará de la lista."
        )

        col_f, col_d = st.columns([2, 1])
        with col_f:
            archivo_ticket = st.file_uploader(
                "Sube la foto o PDF del ticket",
                type=["png", "jpg", "jpeg", "pdf"],
            )
        with col_d:
            fecha_ticket = st.date_input("Fecha de la compra", value=date.today())
            st.session_state["fecha_compra_ticket"] = str(fecha_ticket)

        texto_pegado = st.text_area(
            "O pega aquí las líneas del ticket directamente:",
            placeholder="CONTRAMUSLO POLLO 1KG\nYOGUR GRIEGO LIGERO\nBOLSA BASURA 30L\nPELADOR VERDURAS\nLENTEJAS COCIDAS",
            height=100,
        )

        if st.button("🔍 Analizar Ticket con IA"):
            if not archivo_ticket and not texto_pegado.strip():
                st.warning("Adjunta un archivo o pega el texto del ticket.")
            else:
                with st.spinner("Procesando ticket y clasificando productos..."):
                    items_detectados = procesar_ticket_con_ia(
                        file_upload=archivo_ticket, texto_raw=texto_pegado
                    )
                    st.session_state["ticket_procesado"] = items_detectados

        # Vista previa y confirmación de los productos detectados
        if "ticket_procesado" in st.session_state and st.session_state["ticket_procesado"]:
            items = st.session_state["ticket_procesado"]
            st.success(f"Se han identificado {len(items)} productos en el ticket.")

            st.write("### Vista previa de clasificación:")
            for idx, prod in enumerate(items):
                es_alim = prod.get("es_alimentacion", True)
                icono_tipo = "🥗 Comida" if es_alim else "🧼 Hogar/Limpieza"
                ubicacion = prod.get("ubicacion_defecto", "despensa")
                indiv = " | 🐟 Indivisible" if prod.get("es_indivisible") else ""

                st.markdown(
                    f"**{idx + 1}. {prod.get('nombre_limpio', prod.get('texto_ticket'))}** "
                    f"({icono_tipo})  \n"
                    f"📍 Destino: `{ubicacion}` | Cantidad: `{prod.get('cantidad_aprox', '1 ud')}`{indiv}"
                )

            st.divider()
            if st.button("💾 Confirmar e incorporar a Inventario y Despensa"):
                with st.spinner("Guardando en base de datos..."):
                    res = procesar_y_guardar_ticket_items(items)
                    st.success(
                        f"¡Listo! {res['inventario']} alimentos añadidos a la despensa, "
                        f"{res['hogar_omitido']} productos de hogar filtrados, "
                        f"y {res['lista_tachada']} ítems tachados automáticamente de tu lista."
                    )
                    st.session_state["ticket_procesado"] = []
                    st.rerun()

    # -------------------------------------------------------------------------
    # TAB 3: PLAN SEMANAL BATCH COOKING
    # -------------------------------------------------------------------------
    with tab_plan:
        st.subheader("Planificador Batch Cooking")
        st.info(
            "En la Fase 3, aquí podrás generar planes semanales automáticos con la IA que cuadren las 1.700 kcal de Gonzalo y las 1.350 kcal de Marta."
        )

    # -------------------------------------------------------------------------
    # TAB 4: MEMORIA Y DICCIONARIO DE TICKETS
    # -------------------------------------------------------------------------
    with tab_dicc:
        st.subheader("📖 Diccionario de Supermercados Aprendido")
        st.caption("Memoria acumulada de cómo traduce la IA los nombres de ticket a alimentos reales.")
        try:
            dicc_items = get_diccionario_tickets()
            if dicc_items:
                for d in dicc_items:
                    tipo_txt = "Comida" if d.get("es_alimentacion") else "Hogar"
                    st.markdown(
                        f"- **{d['texto_ticket']}** ➔ `{d['nombre_limpio']}` "
                        f"({tipo_txt} | Ubicación: {d.get('ubicacion_defecto')})"
                    )
            else:
                st.info("Aún no hay productos en el diccionario. Se irán guardando automáticamente con cada ticket.")
        except Exception as e:
            st.error(f"Error al cargar diccionario: {e}")
