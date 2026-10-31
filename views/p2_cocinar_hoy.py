import json
import re
from datetime import date, datetime, timedelta

import streamlit as st

import ai_engine
from database import (
    add_item_inventario,
    add_items_inventario,
    add_receta,
    add_registro_comida,
    coincide_producto,
    delete_all_inventario,
    delete_item_inventario,
    delete_items_inventario,
    get_inventario,
    get_recetas,
    get_registro_comidas_fecha,
    get_registro_comidas_rango,
    mejor_coincidencia_producto,
    update_item_inventario,
    update_receta,
)


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

ETIQUETAS_NUTRIENTES = {
    clave: (etiqueta, unidad) for clave, etiqueta, unidad, _, _ in NUTRIENTES
}

ETIQUETAS_UBICACION = {
    "nevera": "🧊 Nevera",
    "congelador": "❄️ Congelador",
    "despensa": "🥫 Despensa",
    "batch_cocinado": "🥘 Táper Batch",
}

ETIQUETAS_MOMENTO = {
    "desayuno": "☕ Desayuno",
    "comida": "🍽️ Comida",
    "merienda": "🍎 Merienda",
    "cena": "🌙 Cena",
    "snack": "🥜 Snack",
}

OPCIONES_REPARTO = {
    "estandar_55_45": "55% Gonzalo / 45% Marta (guisos)",
    "mitad_50_50": "50% Gonzalo / 50% Marta (piezas iguales)",
    "solo_gonzalo": "Solo Gonzalo",
    "solo_marta": "Solo Marta",
}

FACTORES_REPARTO = {
    "estandar_55_45": (0.55, 0.45),
    "mitad_50_50": (0.50, 0.50),
    "solo_gonzalo": (1.0, 0.0),
    "solo_marta": (0.0, 1.0),
}

UNIDADES_CONTABLES = (
    "comida",
    "comidas",
    "unidad",
    "unidades",
    "bandeja",
    "bandejas",
    "cucharada",
    "cucharadas",
    "lata",
    "latas",
    "bote",
    "botes",
    "taper",
    "táper",
    "tapers",
    "tápers",
    "racion",
    "ración",
    "raciones",
    "cazo",
    "cazos",
    "pieza",
    "piezas",
    "puñado",
    "puñados",
    "sobre",
    "sobres",
    "paquete",
    "paquetes",
)

RE_CANTIDAD_TEXTO = re.compile(r"^\s*(\d+)\s*(.*)$", re.DOTALL)
RE_CANTIDAD_NUM = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(.*)$", re.DOTALL)
UNIDADES_PESO = ("g", "kg", "ml", "l")


def _flash(tipo: str, mensaje: str) -> None:
    st.session_state["_flash_p2"] = (tipo, mensaje)


def _mostrar_flash() -> None:
    flash = st.session_state.pop("_flash_p2", None)
    if not flash:
        return
    tipo, mensaje = flash
    if tipo == "success":
        st.success(mensaje)
    elif tipo == "warning":
        st.warning(mensaje)
    elif tipo == "error":
        st.error(mensaje)
    else:
        st.info(mensaje)


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


def _resumen_nutricion(nutricion) -> str:
    nutricion = _nutricion_dict(nutricion)
    partes = []
    kcal = _numero(nutricion.get("kcal"))
    if kcal > 0:
        partes.append(f"{kcal:.0f} kcal")
    proteinas = _numero(nutricion.get("proteinas_g"))
    if proteinas > 0:
        partes.append(f"{proteinas:.0f} g proteína")
    fibra = _numero(nutricion.get("fibra_g"))
    if fibra > 0:
        partes.append(f"{fibra:.1f} g fibra")
    hierro = _numero(nutricion.get("hierro_mg"))
    if hierro > 0:
        partes.append(f"{hierro:.1f} mg hierro")
    return " · ".join(partes) if partes else "sin nutrientes registrados"


def _singularizar(texto: str) -> str:
    palabras = texto.split()
    if not palabras:
        return texto
    palabra = palabras[0]
    irregulares = {
        "raciones": "ración",
        "tápers": "táper",
        "tapers": "táper",
        "cazos": "cazo",
    }
    if palabra in irregulares:
        palabra = irregulares[palabra]
    elif palabra.endswith("es") and len(palabra) > 4:
        palabra = palabra[:-2]
    elif palabra.endswith("s") and len(palabra) > 3:
        palabra = palabra[:-1]
    palabras[0] = palabra
    return " ".join(palabras)


def descontar_racion(cantidad: str) -> str | None:
    """
    Resta una ración a una cantidad textual contable ("3 comidas de pareja").
    Devuelve None cuando el ítem se agota (o la cantidad no es fraccionable)
    y debe borrarse del inventario.
    """
    texto = str(cantidad or "").strip()
    if not texto:
        return None

    match = RE_CANTIDAD_TEXTO.match(texto)
    if not match:
        return None

    actual = int(match.group(1))
    resto = match.group(2).strip()
    if actual <= 1:
        return None

    if not resto.lower().startswith(UNIDADES_CONTABLES):
        return None

    nuevas = actual - 1
    if nuevas == 1:
        resto = _singularizar(resto)
    return f"{nuevas} {resto}".strip()


def _parsear_cantidad(cantidad) -> tuple[float | None, str]:
    """Separa '3 comidas de pareja' en (3.0, 'comidas de pareja')."""
    texto = str(cantidad or "").strip()
    if not texto:
        return None, ""
    match = RE_CANTIDAD_NUM.match(texto)
    if not match:
        return None, texto
    return _numero(match.group(1)), match.group(2).strip()


def _formatear_numero(numero: float) -> str:
    if abs(float(numero) - round(float(numero))) < 1e-6:
        return str(int(round(float(numero))))
    return f"{float(numero):.2f}".rstrip("0").rstrip(".")


def _es_unidad_peso(resto: str) -> bool:
    return str(resto or "").strip().lower().startswith(UNIDADES_PESO)


def _permite_parcial(item: dict) -> bool:
    """True si el ítem se puede consumir solo en parte (no indivisible y >1)."""
    numero, _ = _parsear_cantidad(item.get("cantidad_aprox"))
    if item.get("es_indivisible"):
        return False
    return bool(numero is not None and numero > 1)


def _escalar_nutricion(nutricion, factor: float) -> dict:
    factor = max(0.0, float(factor))
    resultado: dict = {}
    for clave, valor in _nutricion_dict(nutricion).items():
        numero = _numero(valor)
        if numero <= 0:
            continue
        resultado[clave] = round(numero * factor, 2)
    return resultado


def consumir_cantidad(item: dict, cantidad_consumida: float) -> str:
    """
    Descuenta una cantidad concreta (puede ser parcial) del ítem y devuelve
    un texto con el resultado. Si se agota o no es fraccionable, borra el ítem.
    """
    numero, resto = _parsear_cantidad(item.get("cantidad_aprox"))
    if numero is None or cantidad_consumida >= numero or not _permite_parcial(item):
        delete_item_inventario(item["id"])
        return "se ha agotado"

    restante = numero - cantidad_consumida
    resto_nuevo = _singularizar(resto) if abs(restante - 1) < 1e-6 else resto
    nueva_cantidad = f"{_formatear_numero(restante)} {resto_nuevo}".strip()
    update_item_inventario(item["id"], {"cantidad_aprox": nueva_cantidad})
    return f"quedan {nueva_cantidad}"


def _repartir_nutricion(nutricion, tipo_reparto: str) -> tuple[dict, dict]:
    nutricion = _nutricion_dict(nutricion)
    factor_g, factor_m = FACTORES_REPARTO.get(
        tipo_reparto, FACTORES_REPARTO["estandar_55_45"]
    )
    gonzalo: dict = {}
    marta: dict = {}
    for clave, valor in nutricion.items():
        numero = _numero(valor)
        if numero <= 0:
            continue
        if factor_g > 0:
            gonzalo[clave] = round(numero * factor_g, 2)
        if factor_m > 0:
            marta[clave] = round(numero * factor_m, 2)
    return gonzalo, marta


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


def _consumir_del_inventario(item: dict) -> str:
    """Descuenta una ración del ítem. Devuelve un texto con el resultado."""
    nueva_cantidad = descontar_racion(item.get("cantidad_aprox"))
    if nueva_cantidad:
        update_item_inventario(item["id"], {"cantidad_aprox": nueva_cantidad})
        return f"quedan {nueva_cantidad}"
    delete_item_inventario(item["id"])
    return "se ha agotado"


def _etiqueta_item(item: dict) -> str:
    ubicacion = ETIQUETAS_UBICACION.get(
        str(item.get("ubicacion") or ""), "📦 Inventario"
    )
    nombre = str(item.get("nombre") or "Sin nombre").strip()
    partes = [f"{ubicacion} · {nombre}"]
    cantidad = str(item.get("cantidad_aprox") or "").strip()
    if cantidad:
        partes.append(cantidad)
    if item.get("fecha_cocinado"):
        _, texto, icono = calcular_antiguedad(item.get("fecha_cocinado"))
        partes.append(f"{icono} {texto}")
    return " — ".join(partes)


def _registros_editor(editado) -> list[dict]:
    """Normaliza el resultado de st.data_editor a una lista de diccionarios."""
    if hasattr(editado, "to_dict"):
        try:
            return list(editado.to_dict("records"))
        except (TypeError, ValueError):
            return []
    if isinstance(editado, list):
        return [fila for fila in editado if isinstance(fila, dict)]
    return []


def _opciones_inventario(items: list[dict]) -> dict[str, dict]:
    orden = {"batch_cocinado": 0, "nevera": 1, "congelador": 2, "despensa": 3}
    opciones: dict[str, dict] = {}
    for item in sorted(
        items,
        key=lambda i: (
            orden.get(str(i.get("ubicacion") or ""), 9),
            str(i.get("nombre") or "").lower(),
        ),
    ):
        item_id = str(item.get("id") or "")
        if item_id:
            opciones[item_id] = item
    return opciones


def _buscar_receta_por_nombre(nombre: str, recetas: list[dict]) -> dict | None:
    for receta in recetas or []:
        if coincide_producto(nombre, str(receta.get("titulo") or "")):
            return receta
    return None


def _buscar_item_inventario(
    nombre: str, items: list[dict], excluir: set | None = None
) -> dict | None:
    """
    Busca el ítem de inventario que corresponde a un nombre. Primero prueba el
    cruce exacto por palabras y, si no hay, la mejor coincidencia difusa para
    emparejar variaciones (ej. 'pavo marinado' -> 'Pechuga de pavo').
    """
    excluir = excluir or set()
    candidatos: list[tuple[str, str]] = []
    por_id: dict[str, dict] = {}
    for item in items or []:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in excluir:
            continue
        if str(item.get("ubicacion") or "") == "batch_cocinado":
            continue
        nombre_item = str(item.get("nombre") or "")
        if coincide_producto(nombre, nombre_item):
            return item
        candidatos.append((item_id, nombre_item))
        por_id[item_id] = item

    clave, _ = mejor_coincidencia_producto(nombre, candidatos, umbral=0.5)
    if clave:
        return por_id.get(clave)
    return None


def _marcar_todos(ubicacion: str, items: list):
    """Callback de 'Seleccionar todos': marca o desmarca cada checkbox de la pestaña."""
    valor = bool(st.session_state.get(f"selall_{ubicacion}", False))
    for item in items:
        st.session_state[f"sel_{item['id']}"] = valor


def render_lista_items(
    items: list, ubicacion: str, etiqueta: str, es_batch: bool = False
):
    """Renderiza una lista de alimentos con selección múltiple, consumo y borrado."""
    selall_key = f"selall_{ubicacion}"
    if not items:
        st.session_state.pop(selall_key, None)
        st.info("No hay ítems registrados en esta sección.")
        return

    st.checkbox(
        f"Seleccionar todos ({len(items)})",
        key=selall_key,
        on_change=_marcar_todos,
        args=(ubicacion, items),
    )

    for item in items:
        col_sel, col_info, col_action = st.columns([1, 6, 2])

        with col_sel:
            st.checkbox(
                "Seleccionar",
                key=f"sel_{item['id']}",
                label_visibility="collapsed",
            )

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
            if st.button(
                "🗑️ Gastar",
                key=f"del_{item['id']}",
                width="stretch",
            ):
                delete_item_inventario(item["id"])
                st.toast(f"'{nombre}' consumido/eliminado de la despensa.")
                st.rerun()

        st.divider()

    seleccionados = [
        item for item in items if st.session_state.get(f"sel_{item['id']}")
    ]

    col_info_sel, col_btn_sel = st.columns([3, 2])
    with col_info_sel:
        st.caption(f"{len(seleccionados)} de {len(items)} seleccionados")
    with col_btn_sel:
        if st.button(
            f"🗑️ Borrar seleccionados ({len(seleccionados)})",
            key=f"del_sel_{ubicacion}",
            disabled=not seleccionados,
            width="stretch",
        ):
            n_borrados = delete_items_inventario([it["id"] for it in seleccionados])
            st.toast(f"{n_borrados} producto(s) borrados de {etiqueta}.")
            st.rerun()

    with st.expander(f"⚠️ Vaciar la pestaña {etiqueta}"):
        st.caption(
            f"Se borrarán los {len(items)} productos de {etiqueta}. "
            "Esta acción no se puede deshacer."
        )
        confirmar_tab = st.checkbox(
            "Confirmo que quiero vaciar esta pestaña",
            key=f"conf_tab_{ubicacion}",
        )
        if st.button(
            f"🗑️ Vaciar {etiqueta}",
            key=f"wipe_{ubicacion}",
            disabled=not confirmar_tab,
            width="stretch",
        ):
            n_borrados = delete_all_inventario(ubicacion)
            st.toast(f"{n_borrados} producto(s) borrados. Pestaña vaciada.")
            st.rerun()


# =============================================================================
# PASO 4.1 (A): REGISTRAR COCINADO
# =============================================================================
def _render_registrar_cocinado(recetas: list[dict]) -> None:
    st.subheader("🍳 Registrar Cocinado")
    st.caption(
        "Guarda el día exacto en que se cocinó, actualiza la receta y crea los "
        "tápers en el inventario con su fecha de cocinado."
    )

    if not recetas:
        st.info(
            "Todavía no hay recetas. Crea una en **🛒 Compra → 🍲 Recetas y Batch** "
            "para poder registrar el cocinado."
        )
        return

    recetas_ordenadas = sorted(
        recetas,
        key=lambda r: (
            not bool(r.get("aprobada")),
            str(r.get("titulo") or "").lower(),
        ),
    )
    opciones = {str(r.get("id")): r for r in recetas_ordenadas if r.get("id")}
    if not opciones:
        st.info("Las recetas cargadas no tienen identificador válido.")
        return

    def _etiqueta_receta(receta_id: str) -> str:
        receta = opciones[receta_id]
        comidas = max(
            1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1)
        )
        estado = "✅" if receta.get("aprobada") else "⏳"
        return f"{estado} {receta.get('titulo') or 'Receta'} · {comidas} comidas"

    receta_id = st.selectbox(
        "Receta cocinada",
        list(opciones.keys()),
        format_func=_etiqueta_receta,
        key="cocinado_receta_id",
    )
    receta = opciones[receta_id]
    comidas_receta = max(
        1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1)
    )

    col_fecha, col_comidas = st.columns(2)
    with col_fecha:
        fecha_cocinado = st.date_input(
            "Fecha de cocinado",
            value=date.today(),
            key=f"cocinado_fecha_{receta_id}",
        )
    with col_comidas:
        comidas = st.number_input(
            "Tápers / comidas de pareja a guardar",
            min_value=1,
            max_value=20,
            value=comidas_receta,
            step=1,
            key=f"cocinado_comidas_{receta_id}",
        )

    destino = st.selectbox(
        "¿Dónde guardamos los tápers?",
        ["batch_cocinado", "nevera", "congelador"],
        format_func=lambda valor: {
            "batch_cocinado": "🥘 Tápers Batch (recomendado)",
            "nevera": "🧊 Nevera (para gastar esta semana)",
            "congelador": "❄️ Congelador (para más adelante)",
        }[valor],
        key=f"cocinado_destino_{receta_id}",
    )

    nutricion = _nutricion_dict(receta.get("nutricion_por_comida_pareja"))
    if nutricion:
        st.success(
            f"Nutrición guardada por comida de pareja: {_resumen_nutricion(nutricion)}"
        )
        ajustar = st.checkbox(
            "Ajustar la nutrición antes de guardar los tápers",
            key=f"cocinado_ajustar_{receta_id}",
        )
        if ajustar:
            nutricion = _campos_nutricion(nutricion, f"cocinado_nut_{receta_id}")
    else:
        st.warning(
            "Esta receta no tiene nutrición guardada. Si la rellenas aquí, se "
            "guardará en los tápers para poder sumarla en el Check Comido. "
            "La receta original no se modifica."
        )
        with st.expander("Añadir nutrición por comida de pareja (opcional)"):
            nutricion = _campos_nutricion({}, f"cocinado_nut_{receta_id}")

    if st.button(
        "💾 Guardar cocinado y crear tápers",
        type="primary",
        width="stretch",
        key=f"cocinado_guardar_{receta_id}",
    ):
        filas = []
        for _ in range(int(comidas)):
            filas.append(
                {
                    "nombre": str(receta.get("titulo") or "Receta").strip(),
                    "ubicacion": destino,
                    "cantidad_aprox": "1 comida de pareja",
                    "es_indivisible": False,
                    "nutricion_por_comida_pareja": nutricion or None,
                    "fecha_entrada": date.today().isoformat(),
                    "fecha_cocinado": fecha_cocinado.isoformat(),
                }
            )
        try:
            add_items_inventario(filas)
            update_receta(
                receta_id, {"ultima_vez_cocinada": fecha_cocinado.isoformat()}
            )
        except Exception as exc:
            st.error(f"No se pudo registrar el cocinado: {exc}")
            return

        aviso = (
            ""
            if nutricion
            else " Sin nutrición: el Check Comido no podrá sumar nutrientes de estos tápers."
        )
        _flash(
            "success",
            f"'{receta.get('titulo')}' registrada: {int(comidas)} táper(es) en "
            f"{ETIQUETAS_UBICACION.get(destino, destino)} con fecha "
            f"{fecha_cocinado.isoformat()}.{aviso}",
        )
        st.rerun()


# =============================================================================
# PASO 4.1 (B): CHECK COMIDO
# =============================================================================
def _render_check_comido(inventario: list[dict], recetas: list[dict]) -> None:
    st.subheader("✅ Check Comido")
    st.caption(
        "Descuenta una ración del táper o del inventario y suma los nutrientes "
        "de esa toma a Gonzalo y Marta en el registro del día."
    )

    opciones = _opciones_inventario(inventario)
    if not opciones:
        st.info("No hay alimentos en el inventario para registrar una comida.")
        return

    item_id = st.selectbox(
        "¿Qué has comido?",
        list(opciones.keys()),
        format_func=lambda clave: _etiqueta_item(opciones[clave]),
        key="check_comido_item",
    )
    item = opciones[item_id]

    cantidad_actual = str(item.get("cantidad_aprox") or "S/C")
    st.markdown(
        f"**{item.get('nombre') or 'Alimento'}** · {cantidad_actual} · "
        f"{ETIQUETAS_UBICACION.get(str(item.get('ubicacion') or ''), 'Inventario')}"
    )
    if item.get("fecha_cocinado"):
        _, texto, icono = calcular_antiguedad(item.get("fecha_cocinado"))
        st.caption(f"{icono} {texto} · Cocinado: {item.get('fecha_cocinado')}")

    numero_actual, resto_actual = _parsear_cantidad(item.get("cantidad_aprox"))
    permite_parcial = _permite_parcial(item)
    es_peso = _es_unidad_peso(resto_actual)
    cantidad_consumida = numero_actual if numero_actual is not None else 1.0

    if permite_parcial and numero_actual:
        if es_peso:
            cantidad_consumida = st.number_input(
                f"¿Cuánto has consumido? ({resto_actual})",
                min_value=1.0,
                max_value=float(numero_actual),
                value=float(min(100.0, numero_actual)),
                step=10.0,
                key=f"check_comido_cantidad_{item_id}_{cantidad_actual}",
            )
        else:
            paso = 0.25 if numero_actual <= 4 else 0.5
            cantidad_consumida = st.number_input(
                "¿Cuántas raciones has comido?",
                min_value=0.25,
                max_value=float(numero_actual),
                value=float(min(1.0, numero_actual)),
                step=float(paso),
                key=f"check_comido_cantidad_{item_id}_{cantidad_actual}",
                help=(
                    "Puedes apuntar media ración o solo una parte. El inventario "
                    "y los nutrientes se ajustan a lo que realmente has comido."
                ),
            )
        restante_previsto = float(numero_actual) - float(cantidad_consumida)
        if restante_previsto > 0:
            st.caption(
                f"Se descontarán {_formatear_numero(cantidad_consumida)} de "
                f"{_formatear_numero(numero_actual)}; quedarán "
                f"{_formatear_numero(restante_previsto)} {resto_actual}."
            )
        else:
            st.caption("Con esta cantidad el ítem se agotará y se borrará.")
    elif numero_actual is not None and numero_actual > 0:
        st.caption(
            "Este ítem se consume entero en una toma (no es fraccionable)."
        )

    if not permite_parcial:
        factor_nutricion = 1.0
    elif es_peso:
        factor_nutricion = min(1.0, float(cantidad_consumida) / float(numero_actual))
    else:
        factor_nutricion = float(cantidad_consumida)

    col_fecha, col_momento = st.columns(2)
    with col_fecha:
        fecha_consumo = st.date_input(
            "Fecha de consumo", value=date.today(), key="check_comido_fecha"
        )
    with col_momento:
        momento = st.selectbox(
            "Momento del día",
            list(ETIQUETAS_MOMENTO.keys()),
            format_func=lambda clave: ETIQUETAS_MOMENTO[clave],
            key="check_comido_momento",
        )

    tipo_reparto = st.selectbox(
        "Reparto de la ración",
        list(OPCIONES_REPARTO.keys()),
        format_func=lambda clave: OPCIONES_REPARTO[clave],
        key="check_comido_reparto",
    )

    nutricion_item = _nutricion_dict(item.get("nutricion_por_comida_pareja"))
    recetas_con_nutricion = [
        r
        for r in recetas or []
        if _nutricion_dict(r.get("nutricion_por_comida_pareja"))
        and r.get("id")
    ]

    fuentes = []
    if nutricion_item:
        fuentes.append("item")
    if recetas_con_nutricion:
        fuentes.append("receta")
    fuentes.extend(["manual", "ninguna"])

    etiquetas_fuente = {
        "item": "Del táper / inventario",
        "receta": "De una receta guardada",
        "manual": "Introducir a mano",
        "ninguna": "Sin nutrientes (solo registrar la comida)",
    }

    fuente = st.selectbox(
        "Origen de los nutrientes",
        fuentes,
        format_func=lambda clave: etiquetas_fuente[clave],
        key=f"check_comido_fuente_{item_id}",
    )

    receta_asociada = _buscar_receta_por_nombre(
        str(item.get("nombre") or ""), recetas
    )
    nutricion: dict = {}

    if fuente == "item":
        nutricion = nutricion_item
    elif fuente == "receta":
        mapa_recetas = {str(r.get("id")): r for r in recetas_con_nutricion}
        receta_id = st.selectbox(
            "Receta de la que tomar los nutrientes",
            list(mapa_recetas.keys()),
            format_func=lambda clave: str(
                mapa_recetas[clave].get("titulo") or "Receta"
            ),
            key=f"check_comido_receta_{item_id}",
        )
        receta_asociada = mapa_recetas[receta_id]
        nutricion = _nutricion_dict(
            receta_asociada.get("nutricion_por_comida_pareja")
        )
    elif fuente == "manual":
        with st.expander("Introducir nutrientes de esta comida", expanded=True):
            nutricion = _campos_nutricion(
                {}, f"check_comido_manual_{item_id}"
            )

    nutricion_efectiva = (
        nutricion
        if fuente == "manual"
        else _escalar_nutricion(nutricion, factor_nutricion)
    )

    if nutricion_efectiva:
        gonzalo_previo, marta_previo = _repartir_nutricion(
            nutricion_efectiva, tipo_reparto
        )
        col_g, col_m = st.columns(2)
        with col_g:
            st.caption(f"👨 Gonzalo: {_resumen_nutricion(gonzalo_previo)}")
        with col_m:
            st.caption(f"👩 Marta: {_resumen_nutricion(marta_previo)}")
    else:
        st.caption(
            "Esta toma se registrará en el historial sin sumar nutrientes."
        )

    unidad_consumo = resto_actual or "ración"
    if abs(float(cantidad_consumida) - 1.0) < 1e-6:
        unidad_consumo = _singularizar(unidad_consumo)
    texto_consumo = (
        f"{_formatear_numero(cantidad_consumida)} {unidad_consumo}".strip()
    )

    if st.button(
        f"✅ Registrar comida y descontar {texto_consumo}",
        type="primary",
        width="stretch",
        key=f"check_comido_guardar_{item_id}",
    ):
        gonzalo, marta = _repartir_nutricion(nutricion_efectiva, tipo_reparto)
        registro = {
            "fecha_consumo": fecha_consumo.isoformat(),
            "fecha_cocinado": item.get("fecha_cocinado") or None,
            "momento": momento,
            "receta_id": str(receta_asociada.get("id"))
            if receta_asociada and receta_asociada.get("id")
            else None,
            "tipo_reparto": tipo_reparto,
            "descripcion": (
                f"{str(item.get('nombre') or 'Comida')} ({texto_consumo})"
            ),
            "completado": True,
            "nutricion_gonzalo": gonzalo or None,
            "nutricion_marta": marta or None,
        }
        try:
            add_registro_comida(registro)
            detalle = consumir_cantidad(item, float(cantidad_consumida))
        except Exception as exc:
            st.error(f"No se pudo registrar la comida: {exc}")
            return

        _flash(
            "success",
            f"Comida registrada: {item.get('nombre')} ({texto_consumo}, "
            f"{momento}, {fecha_consumo.isoformat()}). Inventario: {detalle}.",
        )
        st.rerun()


# =============================================================================
# PASO 4.1 (C): FOTO EN ENCIMERA
# =============================================================================
def _render_foto_encimera(inventario: list[dict]) -> None:
    st.subheader("📸 Foto en Encimera")
    st.caption(
        "Haz una foto a los ingredientes crudos. La IA los reconoce, te pregunta "
        "si es una comida de hoy o un batch, descuenta del inventario y registra "
        "la fecha y los nutrientes."
    )

    if not ai_engine.tiene_gemini_key():
        st.warning(
            "Para analizar fotos hace falta la GEMINI_API_KEY configurada en los "
            "secrets. El resto de funciones de la pantalla siguen operativas."
        )

    modo_entrada = st.radio(
        "¿Cómo quieres la foto?",
        ["🖼️ Subir desde el carrete", "📷 Hacer foto con la cámara"],
        horizontal=True,
        key="encimera_modo_entrada",
        disabled=not ai_engine.tiene_gemini_key(),
    )

    if str(modo_entrada).startswith("📷"):
        st.caption(
            "La cámara solo se activa en este modo. Cambia a «Subir desde el "
            "carrete» para apagarla."
        )
        foto_camara = st.camera_input(
            "Foto de la encimera",
            key="encimera_camara",
            disabled=not ai_engine.tiene_gemini_key(),
        )
        archivo = foto_camara
    else:
        archivo = st.file_uploader(
            "Sube una foto desde el carrete o el explorador",
            type=["jpg", "jpeg", "png", "webp"],
            key="encimera_archivo",
            disabled=not ai_engine.tiene_gemini_key(),
        )

    contexto_foto = st.text_input(
        "Contexto para la IA (opcional)",
        placeholder="Ej. El pavo lo he marinado yo con limón y especias",
        key="encimera_contexto",
        help=(
            "Cuéntale a la IA cualquier variación que no se vea en la foto: "
            "marinados, aliños, si algo ya está cocido, etc. Así puede emparejarlo "
            "con el producto correcto del inventario."
        ),
    )

    nombres_inventario = [
        str(item.get("nombre") or "").strip()
        for item in inventario or []
        if str(item.get("ubicacion") or "") != "batch_cocinado"
        and str(item.get("nombre") or "").strip()
    ]

    col_analizar, col_descartar = st.columns(2)
    with col_analizar:
        analizar = st.button(
            "🔎 Analizar foto con IA",
            type="primary",
            width="stretch",
            disabled=archivo is None or not ai_engine.tiene_gemini_key(),
            key="encimera_analizar",
        )
    with col_descartar:
        descartar = st.button(
            "🧹 Descartar análisis",
            width="stretch",
            disabled=not st.session_state.get("_encimera_resultado"),
            key="encimera_descartar",
        )

    if descartar:
        st.session_state.pop("_encimera_resultado", None)
        st.session_state.pop("_encimera_analisis_id", None)
        st.rerun()

    if analizar:
        with st.spinner("Reconociendo ingredientes y estimando nutrientes..."):
            try:
                resultado = ai_engine.reconocer_ingredientes_encimera(
                    archivo,
                    contexto=contexto_foto,
                    nombres_inventario=nombres_inventario,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["_encimera_resultado"] = resultado
                st.session_state["_encimera_analisis_id"] = datetime.now().strftime(
                    "%Y%m%d%H%M%S%f"
                )
                st.rerun()

    resultado = st.session_state.get("_encimera_resultado")
    if not resultado:
        return

    analisis_id = str(st.session_state.get("_encimera_analisis_id") or "actual")
    sufijo = f"_{analisis_id}"

    st.divider()
    st.markdown(f"**Plato detectado:** {resultado.get('descripcion_plato')}")
    st.caption(
        "Revisa y desmarca lo que no quieras descontar del inventario. La IA no "
        "inventa gramos: solo se rellenan si aparecen en el envase."
    )

    opciones_descuento: dict[str, dict] = {}
    for item in inventario or []:
        if str(item.get("ubicacion") or "") == "batch_cocinado":
            continue
        if not item.get("id"):
            continue
        etiqueta = _etiqueta_item(item)
        base = etiqueta
        contador = 2
        while etiqueta in opciones_descuento:
            etiqueta = f"{base} ({contador})"
            contador += 1
        opciones_descuento[etiqueta] = item

    etiqueta_por_id = {
        str(item.get("id")): etiqueta for etiqueta, item in opciones_descuento.items()
    }
    opcion_no_descontar = "🚫 No descontar / no está en inventario"
    lista_opciones = [opcion_no_descontar] + list(opciones_descuento.keys())

    filas = []
    for ingrediente in resultado.get("ingredientes") or []:
        nombre_visible = str(ingrediente.get("nombre") or "").strip()
        nombre_para_cruce = (
            str(ingrediente.get("nombre_inventario") or "").strip()
            or nombre_visible
        )
        match = _buscar_item_inventario(nombre_para_cruce, inventario)
        etiqueta_match = (
            etiqueta_por_id.get(str(match.get("id")), opcion_no_descontar)
            if match
            else opcion_no_descontar
        )
        notas = str(ingrediente.get("notas") or "").strip()
        filas.append(
            {
                "Descontar": True,
                "Ingrediente": nombre_visible,
                "Notas IA": notas,
                "Cantidad": ingrediente.get("cantidad_aprox") or "1 unidad",
                "Gramos (si visibles)": ingrediente.get("gramos_estimados"),
                "Descontar de inventario": etiqueta_match,
            }
        )

    editado = st.data_editor(
        filas,
        hide_index=True,
        width="stretch",
        disabled=[
            "Ingrediente",
            "Notas IA",
            "Cantidad",
            "Gramos (si visibles)",
        ],
        column_config={
            "Descontar": st.column_config.CheckboxColumn("Descontar"),
            "Descontar de inventario": st.column_config.SelectboxColumn(
                "Descontar de inventario",
                options=lista_opciones,
                required=True,
                default=opcion_no_descontar,
                help=(
                    "Puedes cambiar a mano con qué producto del inventario se "
                    "corresponde (útil si la IA no reconoce una variación)."
                ),
            ),
        },
        key=f"editor_encimera{sufijo}",
    )

    if not opciones_descuento:
        st.info(
            "No hay productos en nevera, congelador ni despensa para descontar. "
            "Puedes registrar el análisis como comida o batch igualmente."
        )

    modo = st.selectbox(
        "¿Qué hacemos con lo cocinado?",
        ["comida", "batch"],
        format_func=lambda valor: {
            "comida": "🍽️ Es una comida de hoy (registrar consumo)",
            "batch": "🥘 Es un batch (guardar tápers)",
        }[valor],
        key=f"encimera_modo{sufijo}",
    )

    momento = "comida"
    tipo_reparto = "estandar_55_45"
    fecha_consumo = date.today()
    comidas_batch = 1
    destino_batch = "batch_cocinado"
    fecha_cocinado = date.today()

    if modo == "comida":
        col_fecha, col_momento = st.columns(2)
        with col_fecha:
            fecha_consumo = st.date_input(
                "Fecha de consumo",
                value=date.today(),
                key=f"encimera_fecha_consumo{sufijo}",
            )
        with col_momento:
            momento = st.selectbox(
                "Momento del día",
                list(ETIQUETAS_MOMENTO.keys()),
                format_func=lambda clave: ETIQUETAS_MOMENTO[clave],
                key=f"encimera_momento{sufijo}",
            )
        tipo_reparto = st.selectbox(
            "Reparto de la ración",
            list(OPCIONES_REPARTO.keys()),
            format_func=lambda clave: OPCIONES_REPARTO[clave],
            key=f"encimera_reparto{sufijo}",
        )
    else:
        col_comidas, col_destino = st.columns(2)
        with col_comidas:
            comidas_batch = st.number_input(
                "Comidas de pareja (tápers)",
                min_value=1,
                max_value=20,
                value=max(
                    1, int(_numero(resultado.get("comidas_pareja_estimadas")) or 1)
                ),
                step=1,
                key=f"encimera_comidas_batch{sufijo}",
            )
        with col_destino:
            destino_batch = st.selectbox(
                "Destino de los tápers",
                ["batch_cocinado", "nevera", "congelador"],
                format_func=lambda valor: ETIQUETAS_UBICACION.get(valor, valor),
                key=f"encimera_destino_batch{sufijo}",
            )
        fecha_cocinado = st.date_input(
            "Fecha de cocinado",
            value=date.today(),
            key=f"encimera_fecha_cocinado{sufijo}",
        )

    with st.expander(
        "Nutrición estimada por la IA (por comida de pareja)", expanded=False
    ):
        st.caption(
            "La IA estima a partir de la foto. Revísala y ajusta lo que creas "
            "necesario: se guardará tal cual en el registro."
        )
        nutricion = _campos_nutricion(
            resultado.get("nutricion_por_comida_pareja"),
            f"encimera_nutricion{sufijo}",
        )

    if nutricion:
        gonzalo_previo, marta_previo = _repartir_nutricion(
            nutricion, tipo_reparto if modo == "comida" else "estandar_55_45"
        )
        col_g, col_m = st.columns(2)
        with col_g:
            st.caption(f"👨 Gonzalo: {_resumen_nutricion(gonzalo_previo)}")
        with col_m:
            st.caption(f"👩 Marta: {_resumen_nutricion(marta_previo)}")
    else:
        st.warning(
            "La IA no ha estimado nutrientes. Puedes añadirlos a mano o guardar "
            "sin ellos."
        )

    if st.button(
        "💾 Confirmar y guardar",
        type="primary",
        width="stretch",
        key=f"encimera_confirmar{sufijo}",
    ):
        usados: set = set()
        consumidos: list[str] = []
        no_encontrados: list[str] = []

        try:
            for fila in _registros_editor(editado):
                if not bool(fila.get("Descontar")):
                    continue
                nombre = str(fila.get("Ingrediente") or "").strip()
                etiqueta_elegida = str(
                    fila.get("Descontar de inventario") or ""
                ).strip()
                item = opciones_descuento.get(etiqueta_elegida)
                if not item:
                    no_encontrados.append(nombre)
                    continue
                if str(item.get("id")) in usados:
                    no_encontrados.append(f"{nombre} (ya descontado)")
                    continue
                usados.add(str(item.get("id")))
                detalle = _consumir_del_inventario(item)
                consumidos.append(f"{item.get('nombre')}: {detalle}")

            if modo == "comida":
                gonzalo, marta = _repartir_nutricion(nutricion, tipo_reparto)
                add_registro_comida(
                    {
                        "fecha_consumo": fecha_consumo.isoformat(),
                        "fecha_cocinado": fecha_cocinado.isoformat(),
                        "momento": momento,
                        "receta_id": None,
                        "tipo_reparto": tipo_reparto,
                        "descripcion": str(
                            resultado.get("descripcion_plato")
                            or "Comida de encimera"
                        ),
                        "completado": True,
                        "nutricion_gonzalo": gonzalo or None,
                        "nutricion_marta": marta or None,
                    }
                )
            else:
                filas_batch = []
                for _ in range(int(comidas_batch)):
                    filas_batch.append(
                        {
                            "nombre": str(
                                resultado.get("descripcion_plato")
                                or "Batch de encimera"
                            ),
                            "ubicacion": destino_batch,
                            "cantidad_aprox": "1 comida de pareja",
                            "es_indivisible": False,
                            "nutricion_por_comida_pareja": nutricion or None,
                            "fecha_entrada": date.today().isoformat(),
                            "fecha_cocinado": fecha_cocinado.isoformat(),
                        }
                    )
                add_items_inventario(filas_batch)
        except Exception as exc:
            st.error(f"No se pudo guardar la foto de encimera: {exc}")
            return

        st.session_state.pop("_encimera_resultado", None)
        st.session_state.pop("_encimera_analisis_id", None)

        partes = []
        if modo == "comida":
            partes.append(
                f"Comida registrada ({momento}, {fecha_consumo.isoformat()})"
            )
        else:
            partes.append(
                f"{int(comidas_batch)} táper(es) guardado(s) en "
                f"{ETIQUETAS_UBICACION.get(destino_batch, destino_batch)}"
            )
        if consumidos:
            partes.append("Descontado: " + "; ".join(consumidos))
        if no_encontrados:
            partes.append(
                "No estaban en inventario: " + ", ".join(no_encontrados)
            )
        _flash("success", ". ".join(partes) + ".")
        st.rerun()


def _dias_para_ordenar(item: dict) -> int:
    dias, _, _ = calcular_antiguedad(item.get("fecha_cocinado"))
    return dias


def _render_recetas_rescate(inventario: list[dict], recetas: list[dict]) -> None:
    st.subheader("♻️ Recetas de Rescate (Miércoles/Jueves)")
    st.caption(
        "La IA cruza las sobras de nevera y congelador, la antigüedad de los "
        "tápers y los huecos de macros, vitaminas y minerales de la semana para "
        "proponer cómo cerrarla sin tirar comida."
    )

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    try:
        registros_semana = get_registro_comidas_rango(
            inicio_semana.isoformat(), hoy.isoformat()
        ) or []
    except Exception as exc:
        st.warning(f"No se pudo leer el registro de comidas de la semana: {exc}")
        registros_semana = []

    resumen = ai_engine.resumir_nutricion_semanal(registros_semana, hoy)

    tapers = [
        item
        for item in inventario or []
        if str(item.get("ubicacion") or "") == "batch_cocinado"
    ]
    nevera = [
        item
        for item in inventario or []
        if str(item.get("ubicacion") or "") == "nevera"
    ]
    congelador = [
        item
        for item in inventario or []
        if str(item.get("ubicacion") or "") == "congelador"
    ]
    tapers_ordenados = sorted(tapers, key=_dias_para_ordenar, reverse=True)
    urgentes = [item for item in tapers_ordenados if _dias_para_ordenar(item) >= 3]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tápers", f"{len(tapers)}")
    c2.metric("Urgentes ≥3 días", f"{len(urgentes)}")
    c3.metric("Nevera", f"{len(nevera)}")
    c4.metric("Congelador", f"{len(congelador)}")

    if tapers_ordenados:
        st.markdown("**Sobras que corren más prisa**")
        for item in tapers_ordenados[:5]:
            _, texto, icono = calcular_antiguedad(item.get("fecha_cocinado"))
            nombre = str(item.get("nombre") or "Táper sin nombre").strip()
            st.markdown(f"{icono} **{nombre}** — {texto}")
    else:
        st.info("No hay tápers cocinados en el inventario.")

    with st.expander("📊 Huecos nutricionales de la semana", expanded=False):
        st.caption(
            f"{resumen.get('comidas_registradas', 0)} comida(s) registradas "
            f"desde el lunes {resumen.get('fecha_inicio', '')} hasta hoy "
            f"({resumen.get('dia_fin', '')} {resumen.get('fecha_fin', '')}). "
            f"Faltan {resumen.get('dias_restantes', 0)} día(s) de semana."
        )
        for persona, etiqueta_persona in (
            ("gonzalo", "👨 Gonzalo"),
            ("marta", "👩 Marta"),
        ):
            detalle = (resumen.get("personas") or {}).get(persona) or {}
            st.markdown(f"**{etiqueta_persona}**")
            for clave, (etiqueta, unidad) in ETIQUETAS_NUTRIENTES.items():
                datos = detalle.get(clave)
                if not datos:
                    continue
                total = float(datos.get("total", 0.0))
                objetivo = float(datos.get("objetivo", 0.0))
                porcentaje = float(datos.get("porcentaje", 0.0))
                if datos.get("es_tope"):
                    texto = (
                        f"{etiqueta}: {total:.1f} / {objetivo:.0f} {unidad} "
                        f"(tope, {porcentaje:.0f}%)"
                    )
                else:
                    texto = (
                        f"{etiqueta}: {total:.1f} / {objetivo:.0f} {unidad} "
                        f"({porcentaje:.0f}%)"
                    )
                st.progress(
                    min(max(porcentaje / 100.0, 0.0), 1.0), text=texto
                )
                if datos.get("es_tope") and float(datos.get("exceso", 0.0)) > 0:
                    st.caption(
                        f"⚠️ Superado en {float(datos['exceso']):.1f} {unidad}."
                    )
            st.divider()

    st.divider()
    if not ai_engine.tiene_gemini_key():
        st.warning(
            "Para proponer recetas hace falta la GEMINI_API_KEY configurada en "
            "los secrets. El diagnóstico de sobras y huecos sigue disponible."
        )
    if not inventario:
        st.info(
            "No hay inventario para rescatar. Añade tápers, nevera o congelador "
            "para que la IA pueda proponer recetas con lo que ya tienes."
        )

    contexto_rescate = st.text_input(
        "Contexto para la IA (opcional)",
        placeholder="Ej. Hoy es miércoles, solo tengo 20 minutos y no quiero encender el horno",
        key="rescate_contexto",
        help=(
            "Cuéntale a la IA el tiempo real, el hambre, el momento del día o "
            "cualquier ingrediente que quieras gastar sí o sí."
        ),
    )

    col_generar, col_descartar = st.columns(2)
    with col_generar:
        generar = st.button(
            "♻️ Proponer recetas de rescate",
            type="primary",
            width="stretch",
            disabled=not inventario or not ai_engine.tiene_gemini_key(),
            key="rescate_generar",
        )
    with col_descartar:
        descartar = st.button(
            "🧹 Descartar propuestas",
            width="stretch",
            disabled=not st.session_state.get("_rescate_resultado"),
            key="rescate_descartar",
        )

    if descartar:
        st.session_state.pop("_rescate_resultado", None)
        st.session_state.pop("_rescate_id", None)
        st.rerun()

    if generar:
        with st.spinner("Cruzando sobras, antigüedad y huecos de la semana..."):
            try:
                resultado = ai_engine.proponer_recetas_rescate(
                    inventario,
                    registros_semana=registros_semana,
                    resumen_semanal=resumen,
                    contexto=contexto_rescate,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["_rescate_resultado"] = resultado
                st.session_state["_rescate_id"] = datetime.now().strftime(
                    "%Y%m%d%H%M%S%f"
                )
                st.rerun()

    resultado = st.session_state.get("_rescate_resultado")
    if not resultado:
        return

    sufijo = f"_{st.session_state.get('_rescate_id') or 'actual'}"
    st.divider()
    resumen_situacion = str(resultado.get("resumen_situacion") or "").strip()
    if resumen_situacion:
        st.info(resumen_situacion)

    titulos_existentes = {
        str(receta.get("titulo") or "").strip().lower() for receta in recetas or []
    }

    for indice, receta in enumerate(resultado.get("recetas") or []):
        titulo = str(
            receta.get("titulo") or f"Receta de rescate {indice + 1}"
        ).strip()
        with st.expander(f"{indice + 1}. {titulo}", expanded=(indice == 0)):
            porque = str(receta.get("porque_rescate") or "").strip()
            if porque:
                st.markdown(f"**Por qué ahora:** {porque}")

            momento = str(receta.get("momento_recomendado") or "").strip()
            comidas = max(1, int(_numero(receta.get("comidas_pareja_por_olla")) or 1))
            etiqueta_momento = ETIQUETAS_MOMENTO.get(momento, momento)
            st.caption(
                f"{etiqueta_momento} · {comidas} comida(s) de pareja · "
                "reparto 55% Gonzalo / 45% Marta"
            )

            cubre = receta.get("cubre_huecos") or []
            if cubre:
                st.caption("Cubre: " + ", ".join(str(item) for item in cubre))
            sobras = receta.get("usa_sobras") or []
            if sobras:
                st.caption("Aprovecha: " + ", ".join(str(item) for item in sobras))

            st.markdown("**Ingredientes**")
            for ingrediente in receta.get("ingredientes") or []:
                marca = "✅" if ingrediente.get("del_inventario") else "🛒"
                nombre_ing = str(ingrediente.get("nombre") or "").strip()
                cantidad = str(ingrediente.get("cantidad") or "").strip()
                linea = f"- {marca} **{nombre_ing}**"
                if cantidad:
                    linea += f" — {cantidad}"
                st.markdown(linea)
            st.caption("✅ ya está en tu cocina · 🛒 habría que comprarlo")

            pasos = str(receta.get("pasos_preparacion") or "").strip()
            if pasos:
                st.markdown("**Preparación**")
                st.markdown(pasos)
            guia = str(receta.get("guia_emplatado") or "").strip()
            if guia:
                st.caption(f"🍽️ {guia}")

            nutricion = receta.get("nutricion_por_comida_pareja") or {}
            if nutricion:
                st.markdown(
                    "**Nutrición por comida de pareja:** "
                    + _resumen_nutricion(nutricion)
                )
                gonzalo, marta = _repartir_nutricion(nutricion, "estandar_55_45")
                col_g, col_m = st.columns(2)
                with col_g:
                    st.caption(f"👨 Gonzalo: {_resumen_nutricion(gonzalo)}")
                with col_m:
                    st.caption(f"👩 Marta: {_resumen_nutricion(marta)}")

            aviso = str(receta.get("aviso_clinico") or "").strip()
            if aviso:
                st.warning(f"🩺 {aviso}")

            if st.button(
                "💾 Guardar en el recetario",
                key=f"rescate_guardar{sufijo}_{indice}",
                width="stretch",
            ):
                if titulo.lower() in titulos_existentes:
                    st.warning(
                        "Ya existe una receta con ese título en el recetario."
                    )
                else:
                    ingredientes_json = [
                        {
                            "nombre": str(ing.get("nombre") or "").strip(),
                            "cantidad": str(ing.get("cantidad") or "").strip(),
                        }
                        for ing in receta.get("ingredientes") or []
                        if str(ing.get("nombre") or "").strip()
                    ]
                    try:
                        add_receta(
                            {
                                "titulo": titulo,
                                "tipo": (
                                    "batch_plato_cerrado"
                                    if comidas > 1
                                    else "receta_suelta"
                                ),
                                "aprobada": False,
                                "comidas_pareja_por_olla": comidas,
                                "guia_emplatado": guia or None,
                                "ingredientes_json": ingredientes_json,
                                "pasos_preparacion": pasos or None,
                                "nutricion_por_comida_pareja": nutricion or None,
                            }
                        )
                    except Exception as exc:
                        st.error(f"No se pudo guardar la receta: {exc}")
                    else:
                        _flash(
                            "success",
                            f"Receta '{titulo}' guardada en el recetario "
                            "(sin aprobar).",
                        )
                        st.rerun()


def render():
    st.header("🍳 Cocinar Hoy y Despensa")
    st.caption("Nevera, congelador, despensa y control de fechas de cocinado.")
    _mostrar_flash()

    # Carga única del inventario y las recetas
    try:
        inventario = get_inventario()
    except Exception as e:
        st.error(f"Error al cargar el inventario de Supabase: {e}")
        inventario = []

    try:
        recetas = get_recetas()
    except Exception as e:
        st.warning(f"No se pudieron cargar las recetas: {e}")
        recetas = []

    try:
        comidas_hoy = len(
            get_registro_comidas_fecha(date.today().isoformat()) or []
        )
    except Exception:
        comidas_hoy = 0

    items_nevera = [i for i in inventario if i.get("ubicacion") == "nevera"]
    items_congelador = [
        i for i in inventario if i.get("ubicacion") == "congelador"
    ]
    items_despensa = [i for i in inventario if i.get("ubicacion") == "despensa"]
    items_batch = [
        i for i in inventario if i.get("ubicacion") == "batch_cocinado"
    ]

    # Métricas generales de la cocina
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nevera", f"{len(items_nevera)}")
    c2.metric("Congelador", f"{len(items_congelador)}")
    c3.metric("Despensa", f"{len(items_despensa)}")
    c4.metric("Tápers Batch", f"{len(items_batch)}")

    if comidas_hoy:
        st.caption(f"✅ {comidas_hoy} comida(s) registradas hoy.")

    st.divider()

    tab_acciones, tab_batch, tab_nevera, tab_congelador, tab_despensa, tab_add = (
        st.tabs(
            [
                "🍳 Acciones",
                "🥘 Tápers Batch",
                "🧊 Nevera",
                "❄️ Congelador",
                "🥫 Despensa Seca",
                "➕ Añadir Alimento",
            ]
        )
    )

    with tab_acciones:
        sub_acciones = st.tabs(
            [
                "🍳 Registrar Cocinado",
                "✅ Check Comido",
                "📸 Foto en Encimera",
                "♻️ Recetas de Rescate",
            ]
        )
        with sub_acciones[0]:
            _render_registrar_cocinado(recetas)
        with sub_acciones[1]:
            _render_check_comido(inventario, recetas)
        with sub_acciones[2]:
            _render_foto_encimera(inventario)
        with sub_acciones[3]:
            _render_recetas_rescate(inventario, recetas)

    with tab_batch:
        st.subheader("🥘 Tápers y Raciones Cocinadas")
        st.caption("Control estricto de fechas de cocinado para máxima frescura.")
        render_lista_items(
            items_batch, "batch_cocinado", "Tápers Batch", es_batch=True
        )

    with tab_nevera:
        st.subheader("🧊 Nevera (Frescos)")
        render_lista_items(items_nevera, "nevera", "Nevera")

    with tab_congelador:
        st.subheader("❄️ Congelador")
        render_lista_items(items_congelador, "congelador", "Congelador")

    with tab_despensa:
        st.subheader("🥫 Despensa Seca")
        render_lista_items(items_despensa, "despensa", "Despensa Seca")

    with tab_add:
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
                incluir_fecha = st.checkbox(
                    "¿Es un plato ya cocinado?",
                    value=(ubicacion == "batch_cocinado"),
                )
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
                        st.success(
                            f"'{nombre}' guardado correctamente en {ubicacion}."
                        )
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error al guardar en Supabase: {err}")

    st.divider()
    with st.expander("☠️ Zona peligrosa: borrar TODO el inventario"):
        st.error(
            "Esto vacía Nevera, Congelador, Despensa Seca y Tápers Batch de una sola vez. "
            "La acción no se puede deshacer."
        )
        confirmacion = st.text_input(
            "Escribe BORRAR para confirmar",
            key="confirm_borrar_todo_inventario",
            placeholder="BORRAR",
        )
        if st.button(
            "☠️ Borrar TODO el inventario",
            key="wipe_all_inventario",
            type="primary",
            width="stretch",
            disabled=confirmacion.strip().upper() != "BORRAR",
        ):
            n_borrados = delete_all_inventario()
            st.toast(f"Inventario vaciado: {n_borrados} producto(s) borrados.")
            st.rerun()
