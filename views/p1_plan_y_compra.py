from datetime import date

import pandas as pd
import streamlit as st

from database import (
    get_lista_compra,
    add_item_lista_compra,
    marcar_item_lista_compra,
    delete_item_lista_compra,
    delete_items_lista_compra,
    delete_all_lista_compra,
    procesar_y_guardar_ticket_items,
    get_diccionario_tickets,
)
from ai_engine import procesar_ticket_con_ia, tiene_gemini_key


UBICACIONES_TICKET = ["nevera", "congelador", "despensa", "hogar_no_inventariar"]

ETIQUETAS_UBICACION = {
    "nevera": "🧊 Nevera",
    "congelador": "❄️ Congelador",
    "despensa": "🥫 Despensa",
    "hogar_no_inventariar": "🧼 Hogar (no inventariar)",
}

COLUMNAS_TICKET = [
    "incluir",
    "nombre_limpio",
    "es_alimentacion",
    "ubicacion_defecto",
    "cantidad_aprox",
    "es_indivisible",
    "gramos_habituales",
    "texto_ticket",
    "supermercado",
]


def _plural(cantidad: int, singular: str, plural: str) -> str:
    """Devuelve '1 producto' o '3 productos' según corresponda."""
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _config_columnas_ticket() -> dict:
    """Configuración de la tabla editable de revisión del ticket."""
    return {
        "incluir": st.column_config.CheckboxColumn(
            "✅ Incluir",
            default=True,
            help="Desmarca para no guardar esta fila.",
        ),
        "nombre_limpio": st.column_config.TextColumn(
            "Producto",
            max_chars=80,
            help="Puedes corregir el nombre antes de guardarlo.",
        ),
        "es_alimentacion": st.column_config.CheckboxColumn(
            "🥗 Comida",
            default=True,
            help="Desmarca si es limpieza, higiene u hogar.",
        ),
        "ubicacion_defecto": st.column_config.SelectboxColumn(
            "📍 Destino",
            options=UBICACIONES_TICKET,
            default="despensa",
            format_func=lambda x: ETIQUETAS_UBICACION.get(x, x),
            help="Dónde se guardará en el inventario.",
        ),
        "cantidad_aprox": st.column_config.TextColumn(
            "Cantidad",
            default="1 unidad",
            max_chars=40,
        ),
        "es_indivisible": st.column_config.CheckboxColumn(
            "🐟 Indivisible",
            default=False,
            help="Piezas que se gastan enteras (dorada, pollo entero...).",
        ),
        "gramos_habituales": st.column_config.NumberColumn(
            "Gramos",
            min_value=0,
            max_value=100000,
            step=10,
            format="%d",
        ),
        "texto_ticket": None,
        "supermercado": None,
    }


def _items_ticket_a_dataframe(items: list) -> pd.DataFrame:
    """Convierte los productos detectados por la IA en una tabla editable."""
    filas = []
    for it in items or []:
        ubicacion = it.get("ubicacion_defecto")
        filas.append(
            {
                "incluir": bool(it.get("incluir", True)),
                "nombre_limpio": str(
                    it.get("nombre_limpio") or it.get("texto_ticket") or ""
                ),
                "es_alimentacion": bool(it.get("es_alimentacion", True)),
                "ubicacion_defecto": (
                    ubicacion if ubicacion in UBICACIONES_TICKET else "despensa"
                ),
                "cantidad_aprox": str(it.get("cantidad_aprox") or "1 unidad"),
                "es_indivisible": bool(it.get("es_indivisible", False)),
                "gramos_habituales": it.get("gramos_habituales"),
                "texto_ticket": str(it.get("texto_ticket") or ""),
                "supermercado": str(it.get("supermercado") or "General"),
            }
        )

    df = pd.DataFrame(filas, columns=COLUMNAS_TICKET)
    if not df.empty:
        df["gramos_habituales"] = pd.to_numeric(
            df["gramos_habituales"], errors="coerce"
        )
    return df


def _dataframe_ticket_a_items(
    df: pd.DataFrame, solo_incluidos: bool = True
) -> list[dict]:
    """Convierte la tabla editada en la lista limpia que se guardará en Supabase."""
    items = []
    if df is None or df.empty:
        return items

    for _, row in df.iterrows():
        nombre = str(row.get("nombre_limpio") or "").strip()
        if not nombre:
            continue

        incluir = row.get("incluir")
        incluir = True if pd.isna(incluir) else bool(incluir)
        if solo_incluidos and not incluir:
            continue

        es_alim = row.get("es_alimentacion")
        es_alim = True if pd.isna(es_alim) else bool(es_alim)

        ubicacion = row.get("ubicacion_defecto")
        ubicacion = "despensa" if pd.isna(ubicacion) else str(ubicacion).strip()
        if ubicacion not in UBICACIONES_TICKET:
            ubicacion = "despensa"
        if not es_alim:
            ubicacion = "hogar_no_inventariar"

        indivisible = row.get("es_indivisible")
        indivisible = False if pd.isna(indivisible) else bool(indivisible)

        gramos = row.get("gramos_habituales")
        gramos = None if pd.isna(gramos) else float(gramos)

        cantidad = row.get("cantidad_aprox")
        cantidad = (
            "1 unidad"
            if pd.isna(cantidad) or not str(cantidad).strip()
            else str(cantidad).strip()
        )

        texto = row.get("texto_ticket")
        texto = nombre if pd.isna(texto) or not str(texto).strip() else str(texto).strip()

        supermercado = row.get("supermercado")
        supermercado = (
            "General"
            if pd.isna(supermercado) or not str(supermercado).strip()
            else str(supermercado).strip()
        )

        items.append(
            {
                "incluir": incluir,
                "texto_ticket": texto,
                "nombre_limpio": nombre,
                "es_alimentacion": es_alim,
                "supermercado": supermercado,
                "cantidad_aprox": cantidad,
                "gramos_habituales": gramos,
                "es_indivisible": indivisible,
                "ubicacion_defecto": ubicacion,
            }
        )
    return items


def _marcar_todos_compra(clave: str, items: list):
    """Callback de 'Seleccionar todos' para la lista de la compra."""
    valor = bool(st.session_state.get(f"selall_{clave}", False))
    for item in items:
        st.session_state[f"sel_lc_{item['id']}"] = valor


def _render_items_compra(items: list, clave: str, comprado: bool, vacio_texto: str):
    """Lista los ítems de la compra con selección múltiple y borrado masivo."""
    if not items:
        st.session_state.pop(f"selall_{clave}", None)
        st.caption(vacio_texto)
        return

    st.checkbox(
        f"Seleccionar todos ({len(items)})",
        key=f"selall_{clave}",
        on_change=_marcar_todos_compra,
        args=(clave, items),
    )

    for item in items:
        c_sel, c_check, c_del = st.columns([1, 6, 1])
        with c_sel:
            st.checkbox(
                "Seleccionar",
                key=f"sel_lc_{item['id']}",
                label_visibility="collapsed",
            )
        with c_check:
            if comprado:
                if st.button(
                    f"✔️ ~~{item['item']}~~",
                    key=f"uncheck_{item['id']}",
                    help="Haz clic para devolver a pendientes",
                    width="stretch",
                ):
                    marcar_item_lista_compra(item["id"], comprado=False)
                    st.rerun()
            else:
                if st.button(
                    f"⚪ {item['item']} ({item['categoria']})",
                    key=f"check_{item['id']}",
                    help="Haz clic para marcar como comprado",
                    width="stretch",
                ):
                    marcar_item_lista_compra(item["id"], comprado=True)
                    st.rerun()
        with c_del:
            if st.button("❌", key=f"del_lc_{item['id']}", help="Eliminar este ítem"):
                delete_item_lista_compra(item["id"])
                st.rerun()

    seleccionados = [
        it for it in items if st.session_state.get(f"sel_lc_{it['id']}")
    ]
    if st.button(
        f"🗑️ Borrar seleccionados ({len(seleccionados)})",
        key=f"del_sel_{clave}",
        disabled=not seleccionados,
        width="stretch",
    ):
        n_borrados = delete_items_lista_compra([it["id"] for it in seleccionados])
        st.toast(f"{n_borrados} ítem(s) borrados de la lista.")
        st.rerun()


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
                _render_items_compra(
                    pendientes,
                    "pendientes",
                    comprado=False,
                    vacio_texto="¡Lista vacía! No hay compras pendientes.",
                )
            except Exception as e:
                st.error(f"Error al cargar lista: {e}")

        with col_comp:
            st.subheader("✅ Ya Comprados")
            try:
                comprados = get_lista_compra(comprado=True)
                _render_items_compra(
                    comprados,
                    "comprados",
                    comprado=True,
                    vacio_texto="Aún no has marcado productos como comprados.",
                )
            except Exception as e:
                st.error(f"Error al cargar comprados: {e}")

        st.divider()
        with st.expander("☠️ Zona peligrosa: vaciar la lista de la compra"):
            st.error(
                "Se borrarán TODOS los ítems de la lista (pendientes y comprados). "
                "La acción no se puede deshacer."
            )
            confirmacion_lista = st.text_input(
                "Escribe BORRAR para confirmar",
                key="confirm_borrar_lista_compra",
                placeholder="BORRAR",
            )
            if st.button(
                "☠️ Vaciar toda la lista de la compra",
                key="wipe_lista_compra",
                type="primary",
                width="stretch",
                disabled=confirmacion_lista.strip().upper() != "BORRAR",
            ):
                n_borrados = delete_all_lista_compra()
                st.toast(f"Lista vaciada: {n_borrados} ítem(s) borrados.")
                st.rerun()

    # -------------------------------------------------------------------------
    # TAB 2: LECTOR IA DE TICKETS
    # -------------------------------------------------------------------------
    with tab_ticket:
        st.subheader("🧾 Lector Inteligente de Tickets")
        st.caption(
            "Sube una foto, PDF o pega el texto del ticket de Mercadona, Lidl, Consum o Dia. "
            "La IA separará la comida del hogar, guardará en despensa y tachará de la lista."
        )

        if not tiene_gemini_key():
            st.warning(
                "📷 La lectura de **fotos** de tickets requiere la API Key de Google Gemini (Paso 2.3). "
                "Mientras tanto, puedes **pegar el texto** del ticket o subir el **PDF digital** de la "
                "app del supermercado: el analizador local ya filtra cabeceras, direcciones, IVA y totales."
            )

        resumen_previo = st.session_state.pop("ticket_resumen_guardado", None)
        if resumen_previo:
            st.success(
                f"¡Guardado! "
                f"{_plural(resumen_previo['inventario'], 'alimento añadido', 'alimentos añadidos')} a la despensa, "
                f"{_plural(resumen_previo['hogar_omitido'], 'producto de hogar filtrado', 'productos de hogar filtrados')}, "
                f"{_plural(resumen_previo['lista_tachada'], 'ítem tachado', 'ítems tachados')} de tu lista y "
                f"{_plural(resumen_previo['diccionario'], 'producto aprendido', 'productos aprendidos')} en el diccionario."
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
                st.session_state["ticket_items"] = items_detectados
                st.session_state["ticket_items_original"] = [
                    dict(it) for it in items_detectados
                ]
                st.session_state["_ticket_reset_editor"] = True

        # ---------------------------------------------------------------------
        # Revisión editable antes de guardar (Paso 2.4)
        # ---------------------------------------------------------------------
        items_ticket = st.session_state.get("ticket_items") or []
        if items_ticket:
            if st.session_state.get("_ticket_reset_editor"):
                st.session_state["_ticket_reset_editor"] = False
                st.session_state.pop("editor_ticket", None)

            df_ticket = _items_ticket_a_dataframe(items_ticket)

            st.success(
                f"Se han identificado **{len(df_ticket)} productos**. "
                "Revisa, corrige, añade o descarta filas antes de guardar."
            )
            st.caption(
                "Desmarca **✅ Incluir** para descartar una fila, cambia el **Destino**, "
                "corrige el **Producto** o usa la papelera de la tabla para eliminarla."
            )

            editado = st.data_editor(
                df_ticket,
                key="editor_ticket",
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                column_config=_config_columnas_ticket(),
            )

            items_revisados = _dataframe_ticket_a_items(editado)
            n_incluidos = len(items_revisados)
            n_comida = sum(1 for it in items_revisados if it["es_alimentacion"])
            n_hogar = n_incluidos - n_comida
            n_descartados = max(len(editado) - n_incluidos, 0)

            m1, m2, m3 = st.columns(3)
            m1.metric("Se guardarán", n_incluidos)
            m2.metric("🥗 Comida", n_comida)
            m3.metric("🧼 Hogar", n_hogar)
            if n_descartados:
                st.caption(f"🗑️ {n_descartados} fila(s) descartada(s) o vacía(s).")

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button(
                    "🚫 Descartar todo lo de hogar",
                    width="stretch",
                    help="Quita de la tabla todos los productos marcados como no comida.",
                ):
                    restantes = [
                        it
                        for it in _dataframe_ticket_a_items(editado, solo_incluidos=False)
                        if it["es_alimentacion"]
                    ]
                    st.session_state["ticket_items"] = restantes
                    st.session_state["_ticket_reset_editor"] = True
                    st.rerun()
            with col_b2:
                if st.button(
                    "♻️ Restaurar vista original",
                    width="stretch",
                    help="Vuelve a los productos tal y como los detectó la IA.",
                ):
                    st.session_state["ticket_items"] = [
                        dict(it)
                        for it in st.session_state.get("ticket_items_original", [])
                    ]
                    st.session_state["_ticket_reset_editor"] = True
                    st.rerun()

            st.divider()
            if st.button(
                "💾 Confirmar e incorporar a Inventario y Despensa",
                type="primary",
                width="stretch",
            ):
                if not items_revisados:
                    st.warning(
                        "No hay ninguna fila marcada como **Incluir** con nombre de producto."
                    )
                else:
                    with st.spinner("Guardando en base de datos..."):
                        res = procesar_y_guardar_ticket_items(items_revisados)
                    st.session_state["ticket_resumen_guardado"] = res
                    st.session_state["ticket_items"] = []
                    st.session_state["ticket_items_original"] = []
                    st.session_state["_ticket_reset_editor"] = True
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
