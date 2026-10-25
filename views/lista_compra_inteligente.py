import json
import re
import unicodedata

import pandas as pd
import streamlit as st

from database import (
    add_items_lista_compra,
    coincide_producto,
    get_inventario,
    get_lista_compra,
    get_recetas,
    update_item_lista_compra,
)


PLAN_KEY = "plan_semana_recetas"
QUERY_KEY = "plan"
ORIGEN_PLAN = "plan_recetas"

ESTADO_INVENTARIO = "inventario"
ESTADO_COMPRADO = "comprado"
ESTADO_EN_LISTA = "en_lista"
ESTADO_DESACTUALIZADO = "desactualizado"
ESTADO_FALTANTE = "faltante"

ETIQUETAS_ESTADO = {
    ESTADO_INVENTARIO: "✅ En despensa",
    ESTADO_COMPRADO: "🛍️ Ya comprado",
    ESTADO_EN_LISTA: "📝 Ya en la lista",
    ESTADO_DESACTUALIZADO: "🔄 Actualizar cantidad",
    ESTADO_FALTANTE: "➕ Falta",
}

TOKENS_DESPENSA = {
    "aceite", "ajo", "almendra", "arroz", "atun", "avena", "azucar", "caldo",
    "cacao", "cafe", "conserva", "comino", "cuscus", "especia", "frito",
    "garbanzo", "guisante", "harina", "laurel", "legumbre", "lenteja", "levadura",
    "maiz", "miel", "nuez", "oregano", "pasta", "pimenton", "pimienta", "quinoa",
    "sal", "sardina", "semilla", "te", "tomate", "vinagre",
}

UNIDADES = {
    "g": ("peso", 1.0, "g", "g"),
    "kg": ("peso", 1000.0, "g", "g"),
    "ml": ("volumen", 1.0, "ml", "ml"),
    "l": ("volumen", 1000.0, "ml", "ml"),
    "ud": ("ud", 1.0, "unidad", "unidades"),
    "cda": ("cda", 1.0, "cucharada", "cucharadas"),
    "cdta": ("cdta", 1.0, "cucharadita", "cucharaditas"),
    "lata": ("lata", 1.0, "lata", "latas"),
    "bote": ("bote", 1.0, "bote", "botes"),
    "paquete": ("paquete", 1.0, "paquete", "paquetes"),
    "bandeja": ("bandeja", 1.0, "bandeja", "bandejas"),
    "filete": ("filete", 1.0, "filete", "filetes"),
    "pieza": ("pieza", 1.0, "pieza", "piezas"),
    "loncha": ("loncha", 1.0, "loncha", "lonchas"),
    "diente": ("diente", 1.0, "diente", "dientes"),
    "rama": ("rama", 1.0, "rama", "ramas"),
    "hoja": ("hoja", 1.0, "hoja", "hojas"),
    "taza": ("taza", 1.0, "taza", "tazas"),
    "sobre": ("sobre", 1.0, "sobre", "sobres"),
    "rebanada": ("rebanada", 1.0, "rebanada", "rebanadas"),
    "punado": ("punado", 1.0, "puñado", "puñados"),
    "pizca": ("pizca", 1.0, "pizca", "pizcas"),
}

ALIAS_UNIDADES = {
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g",
    "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg",
    "kilogramos": "kg",
    "ml": "ml", "cc": "ml", "mililitro": "ml", "mililitros": "ml",
    "l": "l", "litro": "l", "litros": "l",
    "u": "ud", "ud": "ud", "uds": "ud", "unidad": "ud", "unidades": "ud",
    "cda": "cda", "cdas": "cda", "cucharada": "cda", "cucharadas": "cda",
    "cdta": "cdta", "cdtas": "cdta", "cucharadita": "cdta",
    "cucharaditas": "cdta",
    "lata": "lata", "latas": "lata",
    "bote": "bote", "botes": "bote",
    "paquete": "paquete", "paquetes": "paquete", "pack": "paquete",
    "packs": "paquete",
    "bandeja": "bandeja", "bandejas": "bandeja",
    "filete": "filete", "filetes": "filete",
    "pieza": "pieza", "piezas": "pieza",
    "loncha": "loncha", "lonchas": "loncha",
    "diente": "diente", "dientes": "diente",
    "rama": "rama", "ramas": "rama",
    "hoja": "hoja", "hojas": "hoja",
    "taza": "taza", "tazas": "taza",
    "sobre": "sobre", "sobres": "sobre",
    "rebanada": "rebanada", "rebanadas": "rebanada",
    "puno": "punado", "punos": "punado", "punado": "punado",
    "punados": "punado",
    "pizca": "pizca", "pizcas": "pizca",
}

PATRON_CANTIDAD = re.compile(
    r"(\d+\s*/\s*\d+|\d+(?:[.,]\d+)?)\s*([a-zA-Záéíóúüñ.]*)",
    re.IGNORECASE,
)


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


def _a_numero(texto: str) -> float:
    texto = str(texto or "").strip().replace(" ", "")
    if not texto:
        raise ValueError("sin número")
    if "/" in texto:
        numerador, denominador = texto.split("/", 1)
        return float(numerador) / float(denominador)
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}\.\d{3}", texto) and not texto.startswith("0."):
        texto = texto.replace(".", "")
    return float(texto)


def _parsear_cantidad(cantidad) -> tuple[float, str] | None:
    if cantidad is None:
        return None
    limpio = re.sub(r"\([^)]*\)", " ", str(cantidad)).strip()
    if not limpio:
        return None
    coincidencia = PATRON_CANTIDAD.search(limpio)
    if not coincidencia:
        return None
    try:
        numero = _a_numero(coincidencia.group(1))
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    unidad = _normalizar(coincidencia.group(2) or "")
    return numero, ALIAS_UNIDADES.get(unidad, unidad)


def _formatear_numero(valor: float) -> str:
    if abs(valor - round(valor)) < 0.005:
        return f"{int(round(valor)):,}".replace(",", ".")
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.rstrip("0").rstrip(",")


def _sumar_cantidades(cantidades: list[str]) -> str:
    totales = {}
    sueltas = []
    for cantidad in cantidades or []:
        parseada = _parsear_cantidad(cantidad)
        if parseada is None:
            texto = str(cantidad or "").strip()
            if texto and texto not in sueltas:
                sueltas.append(texto)
            continue

        numero, unidad = parseada
        if unidad in UNIDADES:
            grupo, factor, singular, plural = UNIDADES[unidad]
            clave = grupo
            if clave not in totales:
                totales[clave] = [0.0, singular, plural]
            totales[clave][0] += numero * factor
        elif unidad:
            clave = f"unidad:{unidad}"
            if clave not in totales:
                totales[clave] = [0.0, unidad, unidad]
            totales[clave][0] += numero
        else:
            clave = "sin_unidad"
            if clave not in totales:
                totales[clave] = [0.0, "", ""]
            totales[clave][0] += numero

    partes = []
    for total, singular, plural in totales.values():
        etiqueta = singular if abs(total - 1.0) < 0.005 else plural
        partes.append(f"{_formatear_numero(total)} {etiqueta}".strip())
    partes.extend(sueltas)
    return " + ".join(partes)


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
            if cantidad:
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


def _buscar_en_lista(nombre: str, items: list[dict]):
    for item in items or []:
        if _coincide(nombre, item.get("item", "")):
            return item
    return None


def _en_lista(nombre: str, items: list[dict]) -> bool:
    return _buscar_en_lista(nombre, items) is not None


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
        cantidad = _sumar_cantidades(grupo["cantidades"])
        if _en_inventario(nombre, inventario):
            estado = ESTADO_INVENTARIO
        elif _en_lista(nombre, comprados):
            estado = ESTADO_COMPRADO
        else:
            existente = _buscar_en_lista(nombre, pendientes)
            if existente is None:
                estado = ESTADO_FALTANTE
            elif (
                str(existente.get("origen") or "") == ORIGEN_PLAN
                and str(existente.get("item") or "").strip()
                != _texto_item(nombre, cantidad)
            ):
                estado = ESTADO_DESACTUALIZADO
            else:
                estado = ESTADO_EN_LISTA
        filas.append(
            {
                "nombre": nombre,
                "cantidad": cantidad,
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


def anadir_faltantes(faltantes: list[dict]) -> tuple[int, int, int]:
    """Añade faltantes y corrige la cantidad de los que ya generó el plan."""
    pendientes = list(get_lista_compra(comprado=False))
    comprados = list(get_lista_compra(comprado=True))

    nuevos = []
    actualizados = 0
    omitidos = 0
    for fila in faltantes or []:
        nombre = str(fila.get("nombre") or "").strip()
        if not nombre:
            continue
        texto = _texto_item(nombre, str(fila.get("cantidad") or "").strip())
        existente = next(
            (item for item in pendientes if _coincide(nombre, item.get("item", ""))),
            None,
        )
        if existente:
            if (
                str(existente.get("origen") or "") == ORIGEN_PLAN
                and str(existente.get("item") or "").strip() != texto
            ):
                update_item_lista_compra(
                    existente["id"],
                    {"item": texto, "categoria": _categoria_para(nombre)},
                )
                existente["item"] = texto
                actualizados += 1
            else:
                omitidos += 1
            continue
        if _en_lista(nombre, comprados):
            omitidos += 1
            continue
        nuevo = {
            "item": texto,
            "categoria": _categoria_para(nombre),
            "origen": ORIGEN_PLAN,
            "comprado": False,
        }
        nuevos.append(nuevo)
        pendientes.append(nuevo)

    if nuevos:
        add_items_lista_compra(nuevos)
    return len(nuevos), actualizados, omitidos


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
        "Las cantidades se suman automáticamente cuando el mismo ingrediente aparece "
        "en varias recetas (por ejemplo, 500 g + 500 g = 1.000 g). Un ingrediente cuenta "
        "como cubierto si ya está en nevera, congelador o despensa (los tápers ya cocinados "
        "no cuentan como ingrediente crudo)."
    )

    faltantes = [fila for fila in filas if fila["estado"] == ESTADO_FALTANTE]
    desactualizados = [
        fila for fila in filas if fila["estado"] == ESTADO_DESACTUALIZADO
    ]
    if desactualizados:
        st.caption(
            f"🔄 {len(desactualizados)} cantidad(es) de la lista no coinciden con las "
            "recetas y se corregirán al sincronizar."
        )

    por_resolver = faltantes + desactualizados
    if not por_resolver:
        st.success("¡No falta ningún ingrediente para estas recetas!")
        return

    if faltantes and desactualizados:
        etiqueta_boton = (
            f"🔄 Sincronizar {len(faltantes)} faltante(s) y "
            f"actualizar {len(desactualizados)} cantidad(es)"
        )
    elif faltantes:
        etiqueta_boton = (
            f"➕ Añadir {len(faltantes)} ingrediente(s) a la Lista de la Compra"
        )
    else:
        etiqueta_boton = (
            f"🔄 Actualizar {len(desactualizados)} cantidad(es) de la lista"
        )

    if st.button(etiqueta_boton, type="primary", width="stretch"):
        with st.spinner("Sincronizando la lista de la compra..."):
            try:
                anadidos, actualizados, omitidos = anadir_faltantes(por_resolver)
            except Exception as exc:
                st.error(f"No se pudo actualizar la lista de la compra: {exc}")
            else:
                partes = []
                if anadidos:
                    partes.append(f"{anadidos} ingrediente(s) añadidos")
                if actualizados:
                    partes.append(f"{actualizados} cantidad(es) actualizada(s)")
                if omitidos:
                    partes.append(f"{omitidos} ya estaban apuntados")
                if anadidos or actualizados:
                    _flash("success", "Lista actualizada: " + ", ".join(partes) + ".")
                else:
                    _flash("info", "Todos los ingredientes ya estaban en la lista.")
                st.rerun()
