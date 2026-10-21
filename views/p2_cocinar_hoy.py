from datetime import datetime, date
import streamlit as st
from database import (
    get_inventario,
    add_item_inventario,
    delete_item_inventario,
)


def calcular_antiguedad(fecha_cocinado_str: str) -> tuple[int, str, str]:
    """
    Dada una fecha de cocinado (YYYY-MM-DD), calcula los días transcurridos
    y devuelve (dias, etiqueta_texto, icono_color).
    """
    if not fecha_cocinado_str:
        return 0, "Sin fecha de cocinado", "⚪"

    try:
        f_cocinado = datetime.strptime(str(fecha_cocinado_str), "%Y-%m-%d").date()
        hoy = date.today()
        dias = (hoy - f_cocinado).days

        if dias < 0:
            return 0, "Cocinada hoy (futuro)", "🟢"
        elif dias == 0:
            return 0, "Cocinada hoy", "🟢"
        elif dias == 1:
            return 1, "Cocinada ayer (1 día)", "🟢"
        elif dias == 2:
            return 2, "Cocinada hace 2 días", "🟢"
        elif 3 <= dias <= 4:
            return dias, f"Consumir pronto ({dias} días)", "🟡"
        else:
            return dias, f"Prioridad gastar ({dias} días)", "🔴"
    except Exception:
        return 0, "Fecha no válida", "⚪"


def render_lista_items(items: list, es_batch: bool = False):
    """Renderiza una lista de alimentos con su estado y botón de consumo/eliminado."""
    if not items:
        st.info("No hay ítems registrados en esta sección.")
        return

    for item in items:
        col_info, col_action = st.columns([3, 1])

        with col_info:
            nombre = item.get("nombre", "Alimento")
            cantidad = item.get("cantidad_aprox", "S/C")
            indivisible = " (Indivisible)" if item.get("es_indivisible") else ""
            f_cocinado = item.get("fecha_cocinado")

            if es_batch or f_cocinado:
                dias, texto_antiguedad, icono = calcular_antiguedad(f_cocinado)
                st.markdown(
                    f"**{nombre}** {indivisible}  \n"
                    f"📦 *Cantidad:* {cantidad} | {icono} **{texto_antiguedad}** *(Cocinado: {f_cocinado or 'N/D'})*"
                )
            else:
                f_entrada = item.get("fecha_entrada", "Sin fecha")
                st.markdown(
                    f"**{nombre}** {indivisible}  \n"
                    f"📦 *Cantidad:* {cantidad} | 📅 *Comprado:* {f_entrada}"
                )

        with col_action:
            if st.button("🗑️ Gastar", key=f"del_{item['id']}"):
                delete_item_inventario(item["id"])
                st.toast(f"'{nombre}' consumido/eliminado de la despensa.")
                st.rerun()

        st.divider()


def render():
    st.header("🍳 Cocinar Hoy y Despensa")
    st.caption("Nevera, congelador, despensa y control de fechas de cocinado.")

    # Carga de inventario
    try:
        items_nevera = get_inventario("nevera")
        items_congelador = get_inventario("congelador")
        items_despensa = get_inventario("despensa")
        items_batch = get_inventario("batch_cocinado")
    except Exception as e:
        st.error(f"Error al cargar el inventario de Supabase: {e}")
        items_nevera, items_congelador, items_despensa, items_batch = [], [], [], []

    # Métricas generales de la cocina
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nevera", f"{len(items_nevera)}")
    c2.metric("Congelador", f"{len(items_congelador)}")
    c3.metric("Despensa", f"{len(items_despensa)}")
    c4.metric("Tápers Batch", f"{len(items_batch)}")

    st.divider()

    subtabs = st.tabs(
        [
            "🥘 Tápers Batch",
            "🧊 Nevera",
            "❄️ Congelador",
            "🥫 Despensa Seca",
            "➕ Añadir Alimento",
        ]
    )

    with subtabs[0]:
        st.subheader("🥘 Tápers y Raciones Cocinadas")
        st.caption("Control estricto de fechas de cocinado para máxima frescura.")
        render_lista_items(items_batch, es_batch=True)

    with subtabs[1]:
        st.subheader("🧊 Nevera (Frescos)")
        render_lista_items(items_nevera)

    with subtabs[2]:
        st.subheader("❄️ Congelador")
        render_lista_items(items_congelador)

    with subtabs[3]:
        st.subheader("🥫 Despensa Seca")
        render_lista_items(items_despensa)

    with subtabs[4]:
        st.subheader("➕ Añadir Alimento o Táper Manualmente")
        with st.form("form_nuevo_inventario", clear_on_submit=True):
            nombre = st.text_input(
                "Nombre del alimento o plato",
                placeholder="Ej. Pechuga de pollo, Táper Lentejas, Dorada...",
            )
            col_u, col_c = st.columns(2)
            with col_u:
                ubicacion = st.selectbox(
                    "Ubicación",
                    ["nevera", "congelador", "despensa", "batch_cocinado"],
                    format_func=lambda x: {
                        "nevera": "🧊 Nevera",
                        "congelador": "❄️ Congelador",
                        "despensa": "🥫 Despensa Seca",
                        "batch_cocinado": "🥘 Táper / Batch Cocinado",
                    }[x],
                )
            with col_c:
                cantidad = st.text_input(
                    "Cantidad aproximada",
                    placeholder="Ej. 2 comidas de pareja, 1 bandeja, 500g...",
                )

            es_indivisible = st.checkbox(
                "Alimento indivisible (se gasta entero en una comida, ej. pescado entero)"
            )

            # Si es un táper o batch, solicita la fecha de cocinado
            fecha_cocinado_val = None
            if ubicacion in ["batch_cocinado", "nevera"]:
                incluir_fecha = st.checkbox("¿Es un plato ya cocinado?", value=(ubicacion == "batch_cocinado"))
                if incluir_fecha:
                    fecha_cocinado_input = st.date_input(
                        "Fecha de cocinado", value=date.today()
                    )
                    fecha_cocinado_val = str(fecha_cocinado_input)

            submitted = st.form_submit_button("💾 Guardar en Inventario")

            if submitted:
                if not nombre.strip():
                    st.error("Introduce el nombre del alimento.")
                else:
                    item_data = {
                        "nombre": nombre.strip(),
                        "ubicacion": ubicacion,
                        "cantidad_aprox": cantidad.strip() or "1 unidad",
                        "es_indivisible": es_indivisible,
                        "fecha_entrada": str(date.today()),
                        "fecha_cocinado": fecha_cocinado_val,
                    }
                    try:
                        add_item_inventario(item_data)
                        st.success(f"'{nombre}' guardado correctamente en {ubicacion}.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error al guardar en Supabase: {err}")
