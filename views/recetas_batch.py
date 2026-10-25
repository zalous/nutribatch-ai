import json

import pandas as pd
import streamlit as st

from database import add_receta, delete_receta, get_recetas, update_receta


TIPOS_RECETA = {
    "batch_plato_cerrado": "🍲 Batch: plato cerrado",
    "batch_componente": "🥣 Batch: componente",
    "receta_suelta": "🍽️ Receta suelta",
    "desayuno": "☕ Desayuno",
    "snack_merienda": "🍎 Snack / merienda",
}

NUTRIENTES = [
    ("kcal", "Calorías", "kcal", 5000.0, 10.0),
    ("proteinas_g", "Proteínas", "g", 400.0, 1.0),
    ("carbohidratos_g", "Carbohidratos", "g", 500.0, 1.0),
    ("grasas_g", "Grasas totales", "g", 300.0, 1.0),
    ("grasas_saturadas_g", "Grasas saturadas", "g", 100.0, 0.5),
    ("fibra_g", "Fibra", "g", 100.0, 0.5),
    ("azucares_g", "Azúcares libres", "g", 100.0, 0.5),
    ("hierro_mg", "Hierro", "mg", 100.0, 0.5),
    ("vitamina_c_mg", "Vitamina C", "mg", 1000.0, 1.0),
    ("calcio_mg", "Calcio", "mg", 3000.0, 10.0),
    ("vitamina_d_ug", "Vitamina D", "µg", 100.0, 0.5),
]

OBJETIVO_KCAL_GONZALO = 1700.0
OBJETIVO_KCAL_MARTA = 1350.0
REPARTO_GONZALO = 0.55
REPARTO_MARTA = 0.45


def _flash(tipo: str, mensaje: str) -> None:
    st.session_state["_flash_recetas"] = (tipo, mensaje)


def _mostrar_flash() -> None:
    flash = st.session_state.pop("_flash_recetas", None)
    if not flash:
        return
    tipo, mensaje = flash
    if tipo == "success":
        st.success(mensaje)
    elif tipo == "warning":
        st.warning(mensaje)
    else:
        st.info(mensaje)


def _numero(valor) -> float:
    if valor is None:
        return 0.0
    try:
        return float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return 0.0


def _comidas_texto(comidas: int) -> str:
    if comidas == 1:
        return "1 comida de pareja"
    return f"{comidas} comidas de pareja"


def _nutricion_dict(valor) -> dict:
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except (TypeError, ValueError):
            return {}
    return valor if isinstance(valor, dict) else {}


def _ingredientes_lista(valor) -> list:
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except (TypeError, ValueError):
            return [valor.strip()] if valor.strip() else []
    if isinstance(valor, dict):
        return [valor]
    return valor if isinstance(valor, list) else []


def _ingredientes_a_texto(valor) -> str:
    if isinstance(valor, str):
        return valor
    lineas = []
    for ingrediente in _ingredientes_lista(valor):
        if isinstance(ingrediente, dict):
            nombre = str(
                ingrediente.get("nombre")
                or ingrediente.get("item")
                or ingrediente.get("alimento")
                or ""
            ).strip()
            cantidad = str(
                ingrediente.get("cantidad")
                or ingrediente.get("cantidad_aprox")
                or ""
            ).strip()
            if nombre and cantidad:
                lineas.append(f"{nombre} | {cantidad}")
            elif nombre:
                lineas.append(nombre)
        else:
            texto = str(ingrediente).strip()
            if texto:
                lineas.append(texto)
    return "\n".join(lineas)


def _parsear_ingredientes(texto: str) -> list[dict]:
    ingredientes = []
    for linea in (texto or "").splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        nombre = limpia
        cantidad = ""
        for separador in ("|", "\t", ";"):
            if separador in limpia:
                nombre, cantidad = limpia.split(separador, 1)
                break
        nombre = nombre.strip()
        if nombre:
            ingredientes.append({"nombre": nombre, "cantidad": cantidad.strip()})
    return ingredientes


def _guia_por_defecto(comidas: int) -> str:
    if comidas == 1:
        return (
            "Divide la olla en 1 táper. En esa comida sirve el 55% a Gonzalo "
            "y el 45% a Marta."
        )
    return (
        f"Divide la olla en {comidas} tápers iguales, uno por comida de pareja. "
        "En cada comida sirve el 55% a Gonzalo y el 45% a Marta."
    )


def _etiqueta_tipo(tipo: str) -> str:
    return TIPOS_RECETA.get(tipo, tipo or "Receta")


def _campos_nutricion(actual: dict, prefijo: str) -> dict:
    actual = _nutricion_dict(actual)
    valores = {}
    columnas = st.columns(2)
    for indice, (clave, etiqueta, unidad, maximo, paso) in enumerate(NUTRIENTES):
        with columnas[indice % 2]:
            valor_actual = min(max(_numero(actual.get(clave)), 0.0), float(maximo))
            valores[clave] = st.number_input(
                f"{etiqueta} ({unidad})",
                min_value=0.0,
                max_value=float(maximo),
                step=float(paso),
                value=valor_actual,
                format="%.1f",
                key=f"{prefijo}_{clave}",
                help="Opcional: deja 0 si no conoces el dato.",
            )
    resultado = {clave: valor for clave, valor in valores.items() if valor > 0}
    conocidas = {clave for clave, _, _, _, _ in NUTRIENTES}
    for clave, valor in actual.items():
        if clave not in conocidas and valor not in (None, ""):
            resultado[clave] = valor
    return resultado


def _tabla_reparto(nutricion: dict, comidas: int) -> pd.DataFrame | None:
    nutricion = _nutricion_dict(nutricion)
    filas = []
    for clave, etiqueta, unidad, _, _ in NUTRIENTES:
        valor = _numero(nutricion.get(clave))
        if valor <= 0:
            continue
        filas.append(
            {
                "Nutriente": f"{etiqueta} ({unidad})",
                "Por comida (pareja)": round(valor, 1),
                "Gonzalo 55%": round(valor * REPARTO_GONZALO, 1),
                "Marta 45%": round(valor * REPARTO_MARTA, 1),
                "Olla completa": round(valor * max(1, comidas), 1),
            }
        )
    if not filas:
        return None
    return pd.DataFrame(filas)


def _render_nutricion(nutricion: dict, comidas: int) -> None:
    nutricion = _nutricion_dict(nutricion)
    if not nutricion:
        st.info(
            "Sin datos nutricionales. Edita la receta para añadir al menos las calorías "
            "y comprobar el reparto 55/45."
        )
        return

    tabla = _tabla_reparto(nutricion, comidas)
    if tabla is not None:
        st.markdown("**Reparto por comida de pareja**")
        st.dataframe(tabla, hide_index=True, width="stretch")

    kcal = _numero(nutricion.get("kcal"))
    if kcal <= 0:
        st.caption("Añade las calorías para ver cuánto aporta esta comida a cada uno.")
        return

    kcal_g = kcal * REPARTO_GONZALO
    kcal_m = kcal * REPARTO_MARTA
    st.markdown(
        f"- **Gonzalo (55%):** {kcal_g:.0f} kcal · "
        f"{kcal_g / OBJETIVO_KCAL_GONZALO * 100:.0f}% de su objetivo diario."
    )
    st.markdown(
        f"- **Marta (45%):** {kcal_m:.0f} kcal · "
        f"{kcal_m / OBJETIVO_KCAL_MARTA * 100:.0f}% de su objetivo diario."
    )
    st.caption(
        f"Olla completa ({_comidas_texto(max(1, comidas))}): "
        f"{kcal * max(1, comidas):.0f} kcal para la pareja; "
        f"Gonzalo {kcal * max(1, comidas) * REPARTO_GONZALO:.0f} kcal y "
        f"Marta {kcal * max(1, comidas) * REPARTO_MARTA:.0f} kcal en total."
    )


def _render_detalle(receta: dict) -> None:
    receta_id = str(receta.get("id"))
    tipo = str(receta.get("tipo") or "")
    aprobada = bool(receta.get("aprobada"))
    comidas = max(1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1))
    nutricion = _nutricion_dict(receta.get("nutricion_por_comida_pareja"))

    estado = "✅ Aprobada" if aprobada else "⏳ Pendiente de aprobar"
    st.caption(f"{_etiqueta_tipo(tipo)} · {estado}")
    cada_uno = (
        "1 comida para cada uno"
        if comidas == 1
        else f"{comidas} comidas para cada uno"
    )
    st.markdown(f"**Rinde:** {_comidas_texto(comidas)}, es decir, {cada_uno}.")

    guia = str(receta.get("guia_emplatado") or "").strip()
    if guia:
        st.markdown(f"**Guía de emplatado:** {guia}")

    ingredientes = _ingredientes_lista(receta.get("ingredientes_json"))
    if ingredientes:
        st.markdown("**Ingredientes**")
        for ingrediente in ingredientes:
            if isinstance(ingrediente, dict):
                nombre = str(
                    ingrediente.get("nombre")
                    or ingrediente.get("item")
                    or ingrediente.get("alimento")
                    or ""
                ).strip()
                cantidad = str(
                    ingrediente.get("cantidad")
                    or ingrediente.get("cantidad_aprox")
                    or ""
                ).strip()
                if nombre and cantidad:
                    st.markdown(f"- {nombre} — {cantidad}")
                elif nombre:
                    st.markdown(f"- {nombre}")
            else:
                texto = str(ingrediente).strip()
                if texto:
                    st.markdown(f"- {texto}")

    pasos = str(receta.get("pasos_preparacion") or "").strip()
    if pasos:
        st.markdown("**Preparación**")
        st.markdown(pasos.replace("\n", "  \n"))

    _render_nutricion(nutricion, comidas)

    st.divider()
    col_editar, col_aprobar = st.columns(2)
    with col_editar:
        if st.button(
            "✏️ Editar receta",
            key=f"editar_{receta_id}",
            width="stretch",
        ):
            st.session_state["receta_editando"] = receta_id
            st.rerun()
    with col_aprobar:
        etiqueta = "🚫 Quitar aprobación" if aprobada else "✅ Aprobar receta"
        if st.button(
            etiqueta,
            key=f"aprobar_{receta_id}",
            width="stretch",
        ):
            try:
                update_receta(receta_id, {"aprobada": not aprobada})
                _flash(
                    "success",
                    "Receta aprobada." if not aprobada else "Receta retirada del catálogo fijo.",
                )
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudo actualizar la receta: {exc}")

    with st.expander("🗑️ Eliminar esta receta"):
        st.warning("Esta acción no se puede deshacer.")
        confirmar = st.checkbox(
            "Confirmo que quiero eliminar esta receta",
            key=f"conf_del_{receta_id}",
        )
        if st.button(
            "🗑️ Eliminar receta definitivamente",
            key=f"borrar_{receta_id}",
            type="primary",
            disabled=not confirmar,
            width="stretch",
        ):
            try:
                delete_receta(receta_id)
                _flash("success", "Receta eliminada.")
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudo eliminar la receta: {exc}")


def _datos_receta(
    titulo: str,
    tipo: str,
    comidas: int,
    aprobada: bool,
    ingredientes_texto: str,
    pasos: str,
    guia: str,
    nutricion: dict,
) -> dict:
    return {
        "titulo": titulo.strip(),
        "tipo": tipo,
        "aprobada": bool(aprobada),
        "comidas_pareja_por_olla": int(comidas),
        "guia_emplatado": guia.strip() or _guia_por_defecto(int(comidas)),
        "ingredientes_json": _parsear_ingredientes(ingredientes_texto),
        "pasos_preparacion": pasos.strip() or None,
        "nutricion_por_comida_pareja": nutricion or None,
    }


def _render_nueva_receta() -> None:
    st.subheader("➕ Nueva receta")
    st.caption(
        "Crea recetas de batch o platos sueltos. La olla se reparte en comidas de pareja "
        "y cada comida se sirve al 55% para Gonzalo y 45% para Marta."
    )

    with st.form("form_nueva_receta", clear_on_submit=True):
        titulo = st.text_input(
            "Título de la receta",
            placeholder="Ej. Lentejas con verduras y contramuslo de pollo",
        )
        col_tipo, col_comidas = st.columns(2)
        with col_tipo:
            tipo = st.selectbox(
                "Tipo de receta",
                list(TIPOS_RECETA.keys()),
                format_func=lambda valor: TIPOS_RECETA[valor],
            )
        with col_comidas:
            comidas = st.number_input(
                "Comidas de pareja por olla",
                min_value=1,
                max_value=20,
                value=3,
                step=1,
            )

        aprobada = st.checkbox(
            "Receta aprobada (entra en el catálogo fijo)",
            value=True,
        )

        ingredientes_texto = st.text_area(
            "Ingredientes (uno por línea; usa | para la cantidad)",
            placeholder=(
                "Contramuslo de pollo | 600 g\n"
                "Lentejas | 300 g\n"
                "Pimiento rojo | 2 unidades\n"
                "Zanahoria | 2 unidades"
            ),
            height=130,
        )
        pasos = st.text_area(
            "Preparación",
            placeholder="Sofríe la verdura, añade las lentejas y el pollo, cubre con agua y cocina 30 minutos.",
            height=110,
        )
        guia = st.text_input(
            "Guía de emplatado (opcional)",
            placeholder="Ej. 3 tápers; Gonzalo 3 cazos y Marta 2 cazos y medio por comida.",
        )

        st.markdown("**Nutrición por comida de pareja (opcional)**")
        st.caption("Rellena solo lo que conozcas. El reparto 55/45 se calcula automáticamente.")
        nutricion = _campos_nutricion({}, "nueva")

        enviado = st.form_submit_button(
            "💾 Guardar receta",
            type="primary",
            width="stretch",
        )

    if not enviado:
        return

    if not titulo.strip():
        st.error("Escribe un título para la receta.")
        return

    datos = _datos_receta(
        titulo,
        tipo,
        int(comidas),
        aprobada,
        ingredientes_texto,
        pasos,
        guia,
        nutricion,
    )
    try:
        add_receta(datos)
    except Exception as exc:
        st.error(f"No se pudo guardar la receta: {exc}")
        return

    if not nutricion.get("kcal"):
        _flash(
            "warning",
            "Receta guardada, pero sin calorías no se puede comprobar el reparto 55/45. "
            "Puedes añadirlas editándola.",
        )
    else:
        _flash("success", "Receta guardada correctamente.")
    st.rerun()


def _render_editar_receta(receta: dict) -> None:
    receta_id = str(receta.get("id"))
    st.subheader(f"✏️ Editando: {receta.get('titulo') or 'Receta'}")
    nutricion_actual = _nutricion_dict(receta.get("nutricion_por_comida_pareja"))

    with st.form(f"form_editar_receta_{receta_id}"):
        titulo = st.text_input(
            "Título de la receta",
            value=str(receta.get("titulo") or ""),
        )
        col_tipo, col_comidas = st.columns(2)
        with col_tipo:
            tipo_actual = str(receta.get("tipo") or "batch_plato_cerrado")
            opciones_tipo = list(TIPOS_RECETA.keys())
            indice_tipo = (
                opciones_tipo.index(tipo_actual) if tipo_actual in opciones_tipo else 0
            )
            tipo = st.selectbox(
                "Tipo de receta",
                opciones_tipo,
                index=indice_tipo,
                format_func=lambda valor: TIPOS_RECETA[valor],
            )
        with col_comidas:
            comidas = st.number_input(
                "Comidas de pareja por olla",
                min_value=1,
                max_value=20,
                value=max(1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1)),
                step=1,
            )

        aprobada = st.checkbox(
            "Receta aprobada (entra en el catálogo fijo)",
            value=bool(receta.get("aprobada")),
        )

        ingredientes_texto = st.text_area(
            "Ingredientes (uno por línea; usa | para la cantidad)",
            value=_ingredientes_a_texto(receta.get("ingredientes_json")),
            height=130,
        )
        pasos = st.text_area(
            "Preparación",
            value=str(receta.get("pasos_preparacion") or ""),
            height=110,
        )
        guia = st.text_input(
            "Guía de emplatado",
            value=str(receta.get("guia_emplatado") or ""),
        )

        st.markdown("**Nutrición por comida de pareja**")
        st.caption("Rellena solo lo que conozcas. El reparto 55/45 se calcula automáticamente.")
        nutricion = _campos_nutricion(nutricion_actual, f"edit_{receta_id}")

        col_guardar, col_cancelar = st.columns(2)
        with col_guardar:
            guardar = st.form_submit_button(
                "💾 Guardar cambios",
                type="primary",
                width="stretch",
            )
        with col_cancelar:
            cancelar = st.form_submit_button(
                "Cancelar",
                width="stretch",
            )

    if cancelar:
        st.session_state.pop("receta_editando", None)
        st.rerun()

    if not guardar:
        return

    if not titulo.strip():
        st.error("El título no puede estar vacío.")
        return

    datos = _datos_receta(
        titulo,
        tipo,
        int(comidas),
        aprobada,
        ingredientes_texto,
        pasos,
        guia,
        nutricion,
    )
    try:
        update_receta(receta_id, datos)
    except Exception as exc:
        st.error(f"No se pudo actualizar la receta: {exc}")
        return

    st.session_state.pop("receta_editando", None)
    _flash("success", "Receta actualizada.")
    st.rerun()


def _render_catalogo(recetas: list[dict]) -> None:
    receta_editando = st.session_state.get("receta_editando")
    if receta_editando:
        receta = next(
            (r for r in recetas if str(r.get("id")) == str(receta_editando)),
            None,
        )
        if receta:
            _render_editar_receta(receta)
            st.divider()
        else:
            st.session_state.pop("receta_editando", None)

    col_buscar, col_filtro = st.columns([3, 2])
    with col_buscar:
        busqueda = st.text_input(
            "Buscar receta",
            placeholder="Ej. lentejas, pollo, desayuno...",
            label_visibility="collapsed",
        )
    with col_filtro:
        solo_aprobadas = st.checkbox("Solo aprobadas", value=False)

    texto_busqueda = busqueda.strip().lower()
    filtradas = []
    for receta in recetas:
        titulo = str(receta.get("titulo") or "").lower()
        if solo_aprobadas and not receta.get("aprobada"):
            continue
        if texto_busqueda and texto_busqueda not in titulo:
            continue
        filtradas.append(receta)

    if not filtradas:
        if recetas:
            st.info("No hay recetas que coincidan con el filtro.")
        else:
            st.info(
                "Aún no hay recetas. Crea la primera en la pestaña **➕ Nueva receta**."
            )
        return

    for receta in filtradas:
        receta_id = str(receta.get("id"))
        if receta_editando and receta_id == str(receta_editando):
            continue
        comidas = max(1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1))
        estado = "✅" if receta.get("aprobada") else "⏳"
        kcal = _numero(
            _nutricion_dict(receta.get("nutricion_por_comida_pareja")).get("kcal")
        )
        detalle_kcal = f" · {kcal:.0f} kcal/comida" if kcal > 0 else ""
        etiqueta = (
            f"{estado} {receta.get('titulo') or 'Receta'} · "
            f"{_comidas_texto(comidas)}{detalle_kcal}"
        )
        with st.expander(etiqueta):
            _render_detalle(receta)


def render():
    st.subheader("🍲 Recetas Aprobadas y Batch Cooking")
    st.caption(
        "Catálogo de recetas con comidas de pareja por olla y reparto 55% Gonzalo / 45% Marta."
    )
    _mostrar_flash()

    try:
        recetas = get_recetas()
    except Exception as exc:
        st.error(f"No se pudieron cargar las recetas: {exc}")
        recetas = []

    recetas = sorted(
        recetas,
        key=lambda r: (
            not bool(r.get("aprobada")),
            str(r.get("titulo") or "").lower(),
        ),
    )

    total = len(recetas)
    aprobadas = sum(1 for r in recetas if r.get("aprobada"))
    batch = sum(
        1
        for r in recetas
        if str(r.get("tipo") or "").startswith("batch")
    )
    col_total, col_aprobadas, col_batch = st.columns(3)
    col_total.metric("Recetas", total)
    col_aprobadas.metric("Aprobadas", aprobadas)
    col_batch.metric("Batch", batch)

    tab_catalogo, tab_nueva = st.tabs(["📚 Catálogo", "➕ Nueva receta"])

    with tab_catalogo:
        _render_catalogo(recetas)

    with tab_nueva:
        _render_nueva_receta()
