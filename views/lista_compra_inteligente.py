import json
import unicodedata

import pandas as pd
import streamlit as st

from database import (
    add_items_lista_compra,
    coincide_producto,
    get_inventario,
    get_lista_compra,
    get_recetas,
)


PLAN_KEY = "plan_semana_recetas"
QUERY_KEY = "plan"
ORIGEN_PLAN = "plan_recetas"

ESTADO_INVENTARIO = "inventario"
ESTADO_COMPRADO = "comprado"
ESTADO_EN_LISTA = "en_lista"
ESTADO_FALTANTE = "faltante"

ETIQUETAS_ESTADO = {
    ESTADO_INVENTARIO: "✅ En despensa",
    ESTADO_COMPRADO: "🛍️ Ya comprado",
    ESTADO_EN_LISTA: "📝 Ya en la lista",
    ESTADO_FALTANTE: "➕ Falta",
}

TOKENS_DESPENSA = {
    "aceite", "ajo", "almendra", "arroz", "atun", "avena", "azucar", "caldo",
    "cacao", "cafe", "conserva", "comino", "cuscus", "especia", "frito",
    "garbanzo", "guisante", "harina", "laurel", "legumbre", "lenteja", "levadura",
    "maiz", "miel", "nuez", "oregano", "pasta", "pimenton", "pimienta", "quinoa",
    "sal", "sardina", "semilla", "te", "tomate", "vinagre",
}


def _flash(tipo: str, mensaje: str) -> None:
    st.session_state["_flash_lista_inteligente"] = (tipo, mensaje)


def _mostrar_flash() -> None:
    flash = st.session_state.pop("_flash_lista_inteligente", None)
    if not flash:
        return
    tipo, mensaje = flash
    if tipo == "success":
        st.success(mensaje)
    elif tipo == "warning":
        st.warning(mensaje)
    else:
        st.info(mensaje)


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    sin_acentos = "".join(
        c
        for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )
    limpio = "".join(
        c if c.isalnum() or c.isspace() else " " for c in sin_acentos.lower()
    )
    return " ".join(limpio.split())


def _singularizar(texto: str) -> str:
    palabras = []
    for palabra in _normalizar(texto).split():
        if len(palabra) > 4 and palabra.endswith("ces"):
            palabra = f"{palabra[:-3]}z"
        elif len(palabra) > 4 and palabra.endswith("es"):
            palabra = palabra[:-2]
        elif len(palabra) > 3 and palabra.endswith("s"):
            palabra = palabra[:-1]
        palabras.append(palabra)
    return " ".join(palabras)


def _coincide(nombre_a: str, nombre_b: str) -> bool:
    if coincide_producto(nombre_a, nombre_b):
        return True
    return coincide_producto(_singularizar(nombre_a), _singularizar(nombre_b))


def _json(valor):
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except (TypeError, ValueError):
            return None
    return valor


def _lista_ingredientes(receta: dict) -> list:
    valor = _json(receta.get("ingredientes_json"))
    if isinstance(valor, dict):
        return [valor]
    return valor if isinstance(valor, list) else []


def _separar_ingrediente(ingrediente) -> tuple[str, str]:
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
        return nombre, cantidad

    texto = str(ingrediente or "").strip()
    for separador in ("|", "\t", ";"):
        if separador in texto:
            nombre, cantidad = texto.split(separador, 1)
            return nombre.strip(), cantidad.strip()
    return texto, ""


def agrupar_ingredientes(recetas: list[dict]) -> list[dict]:
    """Une los ingredientes repetidos de varias recetas conservando el orden."""
    grupos = {}
    for receta in recetas or []:
        titulo = str(receta.get("titulo") or "Receta").strip()
        for ingrediente in _lista_ingredientes(receta):
            nombre, cantidad = _separar_ingrediente(ingrediente)
            if not nombre:
                continue
            clave = _normalizar(nombre)
            if not clave:
                continue
            grupo = grupos.get(clave)
            if grupo is None:
                grupo = {
                    "clave": clave,
                    "nombre": nombre,
                    "cantidades": [],
                    "recetas": [],
                }
                grupos[clave] = grupo
            if cantidad and cantidad not in grupo["cantidades"]:
                grupo["cantidades"].append(cantidad)
            if titulo not in grupo["recetas"]:
                grupo["recetas"].append(titulo)
    return list(grupos.values())


def _en_inventario(nombre: str, inventario: list[dict]) -> bool:
    for item in inventario or []:
        if str(item.get("ubicacion") or "") == "batch_cocinado":
            continue
        if _coincide(nombre, item.get("nombre", "")):
            return True
    return False


def _en_lista(nombre: str, items: list[dict]) -> bool:
    for item in items or []:
        if _coincide(nombre, item.get("item", "")):
            return True
    return False


def construir_estado_plan(
    recetas: list[dict],
    inventario: list[dict],
    pendientes: list[dict],
    comprados: list[dict],
) -> list[dict]:
    """Clasifica cada ingrediente como cubierto, ya listado o faltante."""
    filas = []
    for grupo in agrupar_ingredientes(recetas):
        nombre = grupo["nombre"]
        if _en_inventario(nombre, inventario):
            estado = ESTADO_INVENTARIO
        elif _en_lista(nombre, comprados):
            estado = ESTADO_COMPRADO
        elif _en_lista(nombre, pendientes):
            estado = ESTADO_EN_LISTA
        else:
            estado = ESTADO_FALTANTE
        filas.append(
            {
                "nombre": nombre,
                "cantidad": " + ".join(grupo["cantidades"]),
                "recetas": ", ".join(grupo["recetas"]),
                "estado": estado,
            }
        )
    return filas


def _categoria_para(nombre: str) -> str:
    normalizado = _normalizar(nombre)
    if "congelad" in normalizado:
        return "congelados"
    if set(_singularizar(nombre).split()) & TOKENS_DESPENSA:
        return "despensa"
    return "frescos"


def _texto_item(nombre: str, cantidad: str) -> str:
    return f"{nombre} ({cantidad})" if cantidad else nombre


def anadir_faltantes(faltantes: list[dict]) -> tuple[int, int]:
    """Inserta los faltantes evitando duplicados ya presentes en la lista."""
    existentes = list(get_lista_compra(comprado=False))
    existentes.extend(get_lista_compra(comprado=True))

    nuevos = []
    for fila in faltantes or []:
        nombre = str(fila.get("nombre") or "").strip()
        if not nombre:
            continue
        if _en_lista(nombre, existentes):
            continue
        nuevos.append(
            {
                "item": _texto_item(nombre, str(fila.get("cantidad") or "").strip()),
                "categoria": _categoria_para(nombre),
                "origen": ORIGEN_PLAN,
                "comprado": False,
            }
        )

    if not nuevos:
        return 0, len(faltantes or [])

    add_items_lista_compra(nuevos)
    return len(nuevos), len(faltantes or []) - len(nuevos)


def _plan_desde_url(ids_validos: list[str]) -> list[str]:
    valor = st.query_params.get(QUERY_KEY, "")
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    ids = [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]
    validos = set(ids_validos)
    return [identificador for identificador in ids if identificador in validos]


def _guardar_plan_en_url() -> None:
    seleccion = [str(i) for i in (st.session_state.get(PLAN_KEY) or []) if i]
    if seleccion:
        st.query_params[QUERY_KEY] = ",".join(seleccion)
    else:
        try:
            del st.query_params[QUERY_KEY]
        except KeyError:
            pass


def _etiqueta_receta(receta: dict) -> str:
    estado = "✅" if receta.get("aprobada") else "⏳"
    comidas = _comidas_pareja(receta)
    return (
        f"{estado} {receta.get('titulo') or 'Receta'} · "
        f"{comidas} {'comida' if comidas == 1 else 'comidas'}"
    )


def _comidas_pareja(receta: dict) -> int:
    try:
        comidas = int(float(receta.get("comidas_pareja_por_olla") or 1))
    except (TypeError, ValueError):
        comidas = 1
    return max(1, comidas)


def _tabla_plan(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ingrediente": fila["nombre"],
                "Cantidad": fila["cantidad"] or "—",
                "Estado": ETIQUETAS_ESTADO.get(fila["estado"], fila["estado"]),
                "Recetas": fila["recetas"],
            }
            for fila in filas
        ]
    )


def render() -> None:
    st.subheader("🧠 Segundo Cerebro: de recetas a la compra")
    st.caption(
        "Elige las recetas que vas a cocinar esta semana y la app cruzará sus ingredientes "
        "con la despensa, lo ya comprado y la lista pendiente. Lo que falte se añade con un toque."
    )
    _mostrar_flash()

    try:
        recetas = get_recetas()
        inventario = get_inventario()
        pendientes = get_lista_compra(comprado=False)
        comprados = get_lista_compra(comprado=True)
    except Exception as exc:
        st.error(f"No se pudo preparar el plan de la compra: {exc}")
        return

    if not recetas:
        st.info(
            "Aún no hay recetas. Crea las tuyas en **🍲 Recetas y Batch** y podrás "
            "generar la compra de la semana desde aquí."
        )
        return

    recetas = sorted(
        recetas,
        key=lambda r: (
            not bool(r.get("aprobada")),
            str(r.get("titulo") or "").lower(),
        ),
    )
    mapa = {str(receta.get("id")): receta for receta in recetas}
    ids_validos = list(mapa.keys())

    if PLAN_KEY not in st.session_state:
        st.session_state[PLAN_KEY] = _plan_desde_url(ids_validos)
    else:
        st.session_state[PLAN_KEY] = [
            str(i) for i in (st.session_state.get(PLAN_KEY) or []) if str(i) in mapa
        ]

    seleccion = st.multiselect(
        "Recetas de la semana",
        options=ids_validos,
        format_func=lambda identificador: _etiqueta_receta(mapa[identificador]),
        key=PLAN_KEY,
        on_change=_guardar_plan_en_url,
        placeholder="Elige una o varias recetas del catálogo",
    )

    if not seleccion:
        st.caption(
            "Sin recetas seleccionadas. La lista manual de abajo sigue funcionando con normalidad."
        )
        return

    seleccionadas = [mapa[identificador] for identificador in seleccion]
    filas = construir_estado_plan(
        seleccionadas,
        inventario,
        pendientes,
        comprados,
    )
    if not filas:
        st.info(
            "Las recetas seleccionadas no tienen ingredientes. Añádelos en "
            "**🍲 Recetas y Batch** para poder generar la compra."
        )
        return

    total_comidas = sum(
        _comidas_pareja(receta) for receta in seleccionadas
    )
    st.caption(
        f"{len(seleccionadas)} receta(s) seleccionada(s) · "
        f"{total_comidas} comida(s) de pareja para la semana."
    )

    col_inv, col_comp, col_lista, col_falta = st.columns(4)
    col_inv.metric(
        "En despensa",
        sum(1 for fila in filas if fila["estado"] == ESTADO_INVENTARIO),
    )
    col_comp.metric(
        "Comprados",
        sum(1 for fila in filas if fila["estado"] == ESTADO_COMPRADO),
    )
    col_lista.metric(
        "En lista",
        sum(1 for fila in filas if fila["estado"] == ESTADO_EN_LISTA),
    )
    col_falta.metric(
        "Faltan",
        sum(1 for fila in filas if fila["estado"] == ESTADO_FALTANTE),
    )

    st.dataframe(_tabla_plan(filas), hide_index=True, width="stretch")
    st.caption(
        "Las cantidades son orientativas y se suman cuando el mismo ingrediente aparece "
        "en varias recetas. Un ingrediente cuenta como cubierto si ya está en nevera, "
        "congelador o despensa (los tápers ya cocinados no cuentan como ingrediente crudo)."
    )

    faltantes = [fila for fila in filas if fila["estado"] == ESTADO_FALTANTE]
    if not faltantes:
        st.success("¡No falta ningún ingrediente para estas recetas!")
        return

    if st.button(
        f"➕ Añadir {len(faltantes)} ingrediente(s) a la Lista de la Compra",
        type="primary",
        width="stretch",
    ):
        with st.spinner("Añadiendo los ingredientes que faltan..."):
            try:
                anadidos, omitidos = anadir_faltantes(faltantes)
            except Exception as exc:
                st.error(f"No se pudo actualizar la lista de la compra: {exc}")
            else:
                if anadidos:
                    mensaje = (
                        f"{anadidos} ingrediente(s) añadidos a la Lista de la Compra."
                    )
                    if omitidos:
                        mensaje += f" {omitidos} ya estaban apuntados."
                    _flash("success", mensaje)
                else:
                    _flash("info", "Todos los ingredientes ya estaban en la lista.")
                st.rerun()
