import json
from datetime import date

import streamlit as st

import ai_engine
from database import get_registro_comidas_fecha


PERSONAS = (
    {
        "clave": "gonzalo",
        "nombre": "Gonzalo",
        "emoji": "👨",
        "rango_kcal": "1.700 kcal",
        "nota": "Déficit estricto · LDL y ácido úrico bajo control",
    },
    {
        "clave": "marta",
        "nombre": "Marta",
        "emoji": "👩",
        "rango_kcal": "1.350-1.400 kcal",
        "nota": "Déficit estricto · hierro alto y cenas antirreflujo",
    },
)

MACROS_DIARIOS = (
    ("kcal", "Calorías", "kcal", False),
    ("proteinas_g", "Proteínas", "g", False),
    ("carbohidratos_g", "Carbohidratos complejos", "g", False),
    ("grasas_g", "Grasas totales", "g", False),
    ("grasas_saturadas_g", "Grasas saturadas", "g", True),
    ("fibra_g", "Fibra total", "g", False),
    ("azucares_g", "Azúcares libres", "g", True),
)

ETIQUETAS_MOMENTO = {
    "desayuno": "☕ Desayuno",
    "comida": "🍽️ Comida",
    "merienda": "🍎 Merienda",
    "cena": "🌙 Cena",
    "snack": "🥜 Snack",
}

ETIQUETAS_REPARTO = {
    "estandar_55_45": "55/45",
    "mitad_50_50": "50/50",
    "solo_gonzalo": "Solo Gonzalo",
    "solo_marta": "Solo Marta",
}


def _numero(valor) -> float:
    if valor is None:
        return 0.0
    try:
        return float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return 0.0


def _nutricion_dict(valor) -> dict:
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except (TypeError, ValueError):
            return {}
    return valor if isinstance(valor, dict) else {}


def _sumar_nutricion(acumulado: dict, nutricion) -> None:
    for clave, valor in _nutricion_dict(nutricion).items():
        numero = _numero(valor)
        if numero > 0:
            acumulado[clave] = round(acumulado.get(clave, 0.0) + numero, 2)


def _formatear(valor, unidad: str) -> str:
    numero = _numero(valor)
    if unidad == "kcal":
        texto = f"{numero:,.0f}".replace(",", ".")
    elif abs(numero - round(numero)) < 0.05:
        texto = str(int(round(numero)))
    else:
        texto = f"{numero:.1f}".replace(".", ",")
    return f"{texto} {unidad}".strip()


def _tiene_datos(nutricion: dict, clave: str) -> bool:
    return _numero(nutricion.get(clave)) > 0


def _valor_o_sin_datos(nutricion: dict, clave: str, unidad: str) -> str:
    if not _tiene_datos(nutricion, clave):
        return "sin datos"
    return _formatear(nutricion.get(clave), unidad)


def _barra(
    etiqueta: str,
    total: float,
    objetivo: float,
    unidad: str,
    es_tope: bool = False,
) -> None:
    if objetivo <= 0:
        st.caption(f"{etiqueta}: {_formatear(total, unidad)}")
        return

    ratio = total / objetivo
    if es_tope:
        texto = (
            f"{etiqueta}: {_formatear(total, unidad)} / "
            f"tope {_formatear(objetivo, unidad)}"
        )
        if total > objetivo:
            texto += f" · superado en {_formatear(total - objetivo, unidad)}"
        else:
            texto += f" · margen {_formatear(objetivo - total, unidad)}"
    else:
        texto = (
            f"{etiqueta}: {_formatear(total, unidad)} / "
            f"{_formatear(objetivo, unidad)} · {ratio * 100:.0f}%"
        )
    st.progress(min(max(ratio, 0.0), 1.0), text=texto)


def _resumen_kcal(total: float, objetivo: float) -> tuple[str, str]:
    restante = objetivo - total
    if total <= 0:
        return _formatear(total, "kcal"), f"objetivo {_formatear(objetivo, 'kcal')}"
    if restante >= 0:
        return _formatear(total, "kcal"), f"quedan {_formatear(restante, 'kcal')}"
    return _formatear(total, "kcal"), f"exceso de {_formatear(abs(restante), 'kcal')}"


def _panel_persona(
    persona: dict,
    totales: dict,
    objetivos: dict,
    registros: list[dict],
) -> None:
    clave_persona = persona["clave"]
    nombre_nutricion = f"nutricion_{clave_persona}"
    comidas_con_datos = sum(
        1
        for registro in registros
        if _numero(_nutricion_dict(registro.get(nombre_nutricion)).get("kcal")) > 0
    )

    st.caption(persona["nota"])

    valor_kcal, detalle_kcal = _resumen_kcal(
        _numero(totales.get("kcal")), objetivos["kcal"]
    )
    col_kcal, col_comidas = st.columns(2)
    col_kcal.metric("Calorías del día", valor_kcal, detalle_kcal, delta_color="off")
    col_comidas.metric(
        "Comidas con nutrientes",
        f"{comidas_con_datos}",
        f"de {len(registros)} registrada(s)",
        delta_color="off",
    )

    st.markdown("**Progreso diario**")
    for clave, etiqueta, unidad, es_tope in MACROS_DIARIOS:
        _barra(
            etiqueta,
            _numero(totales.get(clave)),
            _numero(objetivos.get(clave)),
            unidad,
            es_tope=es_tope,
        )

    st.markdown("**Grasas desglosadas**")
    grasa_total = _numero(totales.get("grasas_g"))
    col_sat, col_mono, col_poli = st.columns(3)
    col_sat.metric(
        "Saturadas",
        _valor_o_sin_datos(totales, "grasas_saturadas_g", "g"),
        f"tope {_formatear(objetivos.get('grasas_saturadas_g'), 'g')}",
        delta_color="off",
    )
    col_mono.metric(
        "Monoinsaturadas",
        _valor_o_sin_datos(totales, "grasas_monoinsaturadas_g", "g"),
        (
            f"{_numero(totales.get('grasas_monoinsaturadas_g')) / grasa_total * 100:.0f}% "
            "de las grasas"
            if grasa_total > 0 and _tiene_datos(totales, "grasas_monoinsaturadas_g")
            else None
        ),
        delta_color="off",
    )
    col_poli.metric(
        "Poliinsaturadas",
        _valor_o_sin_datos(totales, "grasas_poliinsaturadas_g", "g"),
        (
            f"{_numero(totales.get('grasas_poliinsaturadas_g')) / grasa_total * 100:.0f}% "
            "de las grasas"
            if grasa_total > 0 and _tiene_datos(totales, "grasas_poliinsaturadas_g")
            else None
        ),
        delta_color="off",
    )
    if _tiene_datos(totales, "omega3_g"):
        st.caption(
            f"Omega-3 (EPA+DHA+ALA): {_formatear(totales.get('omega3_g'), 'g')}."
        )
    else:
        st.caption(
            "Omega-3: sin datos. Se mostrará cuando la receta o el registro lo incluyan."
        )

    st.markdown("**Fibra soluble e insoluble**")
    col_fibra, col_soluble, col_insoluble = st.columns(3)
    col_fibra.metric(
        "Fibra total",
        _valor_o_sin_datos(totales, "fibra_g", "g"),
        f"objetivo {_formatear(objetivos.get('fibra_g'), 'g')}",
        delta_color="off",
    )
    col_soluble.metric(
        "Soluble",
        _valor_o_sin_datos(totales, "fibra_soluble_g", "g"),
        delta_color="off",
    )
    col_insoluble.metric(
        "Insoluble",
        _valor_o_sin_datos(totales, "fibra_insoluble_g", "g"),
        delta_color="off",
    )
    if not (
        _tiene_datos(totales, "fibra_soluble_g")
        or _tiene_datos(totales, "fibra_insoluble_g")
    ):
        st.caption(
            "El desglose soluble/insoluble aparecerá cuando las recetas o los "
            "registros de comida incluyan esos datos."
        )

    if _numero(totales.get("azucares_g")) > _numero(objetivos.get("azucares_g")):
        st.warning(
            "Azúcares libres por encima del tope diario. Revisa dulces, salsas "
            "y ultraprocesados del día."
        )
    if _numero(totales.get("grasas_saturadas_g")) > _numero(
        objetivos.get("grasas_saturadas_g")
    ):
        st.warning(
            "Grasas saturadas por encima del tope. Prioriza AOVE, pescado azul, "
            "frutos secos y carnes magras."
        )


def _tabla_comidas(registros: list[dict]) -> list[dict]:
    filas = []
    for registro in registros:
        gonzalo = _nutricion_dict(registro.get("nutricion_gonzalo"))
        marta = _nutricion_dict(registro.get("nutricion_marta"))
        filas.append(
            {
                "Momento": ETIQUETAS_MOMENTO.get(
                    str(registro.get("momento") or ""),
                    str(registro.get("momento") or "—").capitalize(),
                ),
                "Descripción": str(registro.get("descripcion") or "—"),
                "kcal Gonzalo": round(_numero(gonzalo.get("kcal"))),
                "kcal Marta": round(_numero(marta.get("kcal"))),
                "Reparto": ETIQUETAS_REPARTO.get(
                    str(registro.get("tipo_reparto") or ""), "—"
                ),
            }
        )
    return filas


def render() -> None:
    st.header("📊 Cuadro Clínico y Nutricional")
    st.caption(
        "Panel diario de macros por persona, calculado con el registro real de comidas."
    )

    hoy = date.today()
    col_fecha, col_boton = st.columns([2, 1])
    with col_fecha:
        fecha = st.date_input(
            "Día a revisar",
            value=hoy,
            max_value=hoy,
            key="p4_fecha",
        )
    with col_boton:
        st.write("")
        st.write("")
        if st.button("Volver a hoy", use_container_width=True, key="p4_hoy"):
            st.session_state["p4_fecha"] = hoy
            st.rerun()

    if fecha is None:
        fecha = hoy

    try:
        registros = get_registro_comidas_fecha(fecha.isoformat())
    except Exception as exc:
        st.error(f"No se pudo cargar el registro del día: {exc}")
        return

    totales = {"gonzalo": {}, "marta": {}}
    for registro in registros:
        _sumar_nutricion(totales["gonzalo"], registro.get("nutricion_gonzalo"))
        _sumar_nutricion(totales["marta"], registro.get("nutricion_marta"))

    st.markdown(f"### {fecha.strftime('%d/%m/%Y')}")
    if fecha == hoy:
        st.caption("Hoy")
    if registros:
        st.caption(f"{len(registros)} comida(s) registrada(s) en este día.")
    else:
        st.info(
            "No hay comidas registradas para este día. Usa ✅ Check Comido o el "
            "asistente de voz para apuntar lo que coméis."
        )

    tabs = st.tabs(
        [
            f"{persona['emoji']} {persona['nombre']} ({persona['rango_kcal']})"
            for persona in PERSONAS
        ]
    )
    for tab, persona in zip(tabs, PERSONAS):
        with tab:
            _panel_persona(
                persona,
                totales[persona["clave"]],
                ai_engine.OBJETIVOS_NUTRICIONALES_DIARIOS[persona["clave"]],
                registros,
            )

    if registros:
        with st.expander("🍽️ Comidas del día"):
            st.dataframe(
                _tabla_comidas(registros),
                hide_index=True,
                width="stretch",
            )

    with st.expander("ℹ️ Cómo se calcula este panel"):
        st.markdown(
            """
        - Los totales se suman desde `registro_comidas` para la fecha elegida,
          separando la nutrición de Gonzalo y la de Marta.
        - Los objetivos son los del perfil clínico: Gonzalo 1.700 kcal y Marta
          1.350-1.400 kcal, con sus topes de grasas saturadas y azúcares libres.
        - El desglose de grasas (mono, poli/Omega-3) y de fibra
          (soluble/insoluble) solo aparece si la receta, el táper o el registro
          manual incluyen esos datos; nunca se estiman a ojo.
        - Las grasas saturadas y los azúcares libres son topes máximos: lo
          deseable es no superarlos, no llegar a ellos.
            """
        )
