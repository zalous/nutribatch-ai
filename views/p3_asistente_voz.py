import json
import re
from datetime import date

import streamlit as st

import ai_engine
from database import (
    add_items_lista_compra,
    add_registro_comida,
    coincide_producto,
    delete_item_inventario,
    get_lista_compra,
    get_recetas,
    mejor_coincidencia_producto,
    update_item_inventario,
)


FACTORES_REPARTO = {
    "estandar_55_45": (0.55, 0.45),
    "mitad_50_50": (0.50, 0.50),
    "solo_gonzalo": (1.0, 0.0),
    "solo_marta": (0.0, 1.0),
}

UNIDADES_PESO = ("g", "kg", "ml", "l")

RE_CANTIDAD_NUM = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(.*)$", re.DOTALL)

PALABRAS_IGNORADAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "que", "ya", "se", "ha", "han", "hemos", "me", "lo", "nos", "he",
    "taper", "táper", "tapers", "tápers", "comida", "comidas",
    "racion", "ración", "raciones", "porcion", "porción", "porciones",
    "alimento", "producto", "del", "inventario", "nevera", "congelador",
    "despensa", "batch", "cocinado", "cocinada",
}


def _mostrar_error(exc: Exception) -> None:
    st.error("No se pudo completar la consulta contextual.")
    with st.expander("Detalle técnico"):
        st.code(str(exc)[:600], language=None)


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


def _parsear_cantidad(cantidad) -> tuple[float | None, str]:
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
        "comidas": "comida",
    }
    if palabra in irregulares:
        palabra = irregulares[palabra]
    elif palabra.endswith("es") and len(palabra) > 4:
        palabra = palabra[:-2]
    elif palabra.endswith("s") and len(palabra) > 3:
        palabra = palabra[:-1]
    palabras[0] = palabra
    return " ".join(palabras)


def _unidad_normalizada(unidad: str) -> str:
    texto = str(unidad or "").strip().lower()
    if texto.startswith("kilo"):
        return "kg"
    if texto.startswith("gramo"):
        return "g"
    if texto.startswith("mililitro"):
        return "ml"
    if texto.startswith("litro"):
        return "l"
    return texto


def _es_unidad_peso(resto: str) -> bool:
    return _unidad_normalizada(resto).startswith(UNIDADES_PESO)


def _limpiar_objetivo(texto: str) -> str:
    tokens = []
    for token in re.split(r"\s+", str(texto or "").strip()):
        limpio = token.strip(".,;:¡!¿?()[]").lower()
        if not limpio or limpio in PALABRAS_IGNORADAS:
            continue
        tokens.append(token.strip(".,;:¡!¿?()[]"))
    return " ".join(tokens)


def _clave_orden(item: dict):
    ubicacion = str(item.get("ubicacion") or "").strip().lower()
    prioridad = {
        "batch_cocinado": 0,
        "nevera": 1,
        "congelador": 2,
        "despensa": 3,
    }.get(ubicacion, 9)
    fecha = str(item.get("fecha_cocinado") or "9999-12-31")
    return prioridad, fecha, str(item.get("nombre") or "").lower()


def _buscar_item(nombre: str, inventario: list[dict]) -> dict | None:
    """Busca el táper o alimento del inventario que mejor encaja con el nombre dicho."""
    objetivo = _limpiar_objetivo(nombre)
    if len(objetivo) < 2:
        return None

    items = [item for item in inventario or [] if item.get("id")]
    items.sort(key=_clave_orden)

    for item in items:
        nombre_item = str(item.get("nombre") or "")
        if coincide_producto(objetivo, nombre_item) or coincide_producto(
            nombre, nombre_item
        ):
            return item

    candidatos = []
    por_id = {}
    for item in items:
        item_id = str(item.get("id"))
        candidatos.append((item_id, _limpiar_objetivo(item.get("nombre"))))
        por_id[item_id] = item

    clave, _ = mejor_coincidencia_producto(objetivo, candidatos, umbral=0.55)
    return por_id.get(clave) if clave else None


def _buscar_receta(nombre: str, recetas: list[dict]) -> dict | None:
    objetivo = _limpiar_objetivo(nombre)
    if len(objetivo) < 2:
        return None

    for receta in recetas or []:
        titulo = str(receta.get("titulo") or "")
        if coincide_producto(objetivo, titulo) or coincide_producto(nombre, titulo):
            return receta

    candidatos = []
    por_id = {}
    for receta in recetas or []:
        receta_id = str(receta.get("id") or "")
        if not receta_id:
            continue
        candidatos.append((receta_id, _limpiar_objetivo(receta.get("titulo"))))
        por_id[receta_id] = receta

    clave, _ = mejor_coincidencia_producto(objetivo, candidatos, umbral=0.55)
    return por_id.get(clave) if clave else None


def _convertir_peso(cantidad: float, unidad: str, unidad_actual: str) -> float:
    unidad = _unidad_normalizada(unidad)
    unidad_actual = _unidad_normalizada(unidad_actual)
    if unidad.startswith("kg") and unidad_actual.startswith("g"):
        return cantidad * 1000
    if unidad.startswith("g") and unidad_actual.startswith("kg"):
        return cantidad / 1000
    if unidad.startswith("l") and unidad_actual.startswith("ml"):
        return cantidad * 1000
    if unidad.startswith("ml") and unidad_actual.startswith("l"):
        return cantidad / 1000
    return cantidad


def _consumir_item(
    item: dict, cantidad: float | None, unidad: str | None
) -> tuple[str, float]:
    """
    Descuenta del inventario la cantidad indicada (o una ración si no se indica).
    Devuelve (texto_resultado, factor_nutricional).
    """
    item_id = str(item.get("id") or "")
    actual, resto = _parsear_cantidad(item.get("cantidad_aprox"))

    if not item_id or item.get("es_indivisible") or actual is None or actual <= 0:
        if item_id:
            delete_item_inventario(item_id)
        return "se ha agotado", 1.0

    consumir = float(cantidad) if cantidad and cantidad > 0 else None
    unidad = str(unidad or "").strip().lower()

    if consumir is None:
        if _es_unidad_peso(resto):
            delete_item_inventario(item_id)
            return "se ha agotado", 1.0
        consumir = 1.0
        factor = 1.0
    elif _es_unidad_peso(resto) and unidad and _es_unidad_peso(unidad):
        consumir = _convertir_peso(consumir, unidad, resto)
        factor = min(1.0, consumir / actual)
    elif not _es_unidad_peso(resto) and (not unidad or not _es_unidad_peso(unidad)):
        factor = consumir
    else:
        consumir = 1.0
        factor = 1.0

    if consumir >= actual:
        delete_item_inventario(item_id)
        return "se ha agotado", 1.0

    restante = actual - consumir
    resto_nuevo = _singularizar(resto) if abs(restante - 1) < 1e-6 else resto
    nueva_cantidad = f"{_formatear_numero(restante)} {resto_nuevo}".strip()
    update_item_inventario(item_id, {"cantidad_aprox": nueva_cantidad})
    return f"quedan {nueva_cantidad}", factor


def _escalar_nutricion(nutricion, factor: float) -> dict:
    factor = max(0.0, float(factor))
    resultado: dict = {}
    for clave, valor in _nutricion_dict(nutricion).items():
        numero = _numero(valor)
        if numero <= 0:
            continue
        resultado[clave] = round(numero * factor, 2)
    return resultado


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


def _texto_consumo(cantidad: float | None, unidad: str | None) -> str:
    if cantidad and cantidad > 0:
        unidad = str(unidad or "ración").strip()
        if abs(cantidad - 1) < 1e-6:
            unidad = _singularizar(unidad)
        return f"{_formatear_numero(cantidad)} {unidad}".strip()
    return "1 ración"


def _ya_en_lista(nombre: str, items: list[dict]) -> bool:
    for item in items or []:
        if coincide_producto(nombre, str(item.get("item") or "")):
            return True
    return False


def _ejecutar_lista_compra(resultado: dict, contexto: dict) -> str:
    items = resultado.get("items_lista_compra") or []
    if not items:
        return "⚠️ No he detectado productos que apuntar."

    try:
        pendientes = get_lista_compra(comprado=False) or []
    except Exception:
        pendientes = contexto.get("lista_compra") or []

    nuevos: list[dict] = []
    ya_estaban: list[str] = []
    vistos: list[str] = []
    for item in items:
        nombre = str(item.get("item") or "").strip()
        if len(nombre) < 2:
            continue
        if _ya_en_lista(nombre, pendientes) or _ya_en_lista(nombre, vistos):
            ya_estaban.append(nombre)
            continue
        nuevos.append(
            {
                "item": nombre,
                "categoria": item.get("categoria") or "despensa",
                "origen": "manual_o_voz",
                "comprado": False,
                "fecha_anadido": date.today().isoformat(),
            }
        )
        vistos.append({"item": nombre})

    if not nuevos:
        return "ℹ️ Ya estaban en la lista: " + ", ".join(ya_estaban) + "."

    try:
        add_items_lista_compra(nuevos)
    except Exception as exc:
        return f"⚠️ No se pudo añadir a la lista de la compra: {str(exc)[:200]}"

    añadidos = ", ".join(item["item"] for item in nuevos)
    nota = f"🛒 Añadido a la lista de la compra: {añadidos}."
    if ya_estaban:
        nota += " Ya estaban: " + ", ".join(ya_estaban) + "."
    return nota


def _registrar_check_comido(
    resultado: dict,
    item: dict | None,
    receta: dict | None,
    texto_consumo: str,
    factor: float,
) -> str:
    nutricion_base = {}
    if item:
        nutricion_base = _nutricion_dict(item.get("nutricion_por_comida_pareja"))
    if not nutricion_base and receta:
        nutricion_base = _nutricion_dict(receta.get("nutricion_por_comida_pareja"))

    nutricion = _escalar_nutricion(nutricion_base, factor) if nutricion_base else {}
    gonzalo, marta = _repartir_nutricion(
        nutricion, resultado.get("tipo_reparto") or "estandar_55_45"
    )

    nombre = str(
        (item or {}).get("nombre")
        or (receta or {}).get("titulo")
        or resultado.get("objetivo_inventario")
        or "Comida"
    ).strip()
    descripcion = resultado.get("descripcion_registro") or f"{nombre} ({texto_consumo})"
    fecha_consumo = resultado.get("fecha_consumo") or date.today().isoformat()
    fecha_cocinado = (item or {}).get("fecha_cocinado") or (
        receta or {}
    ).get("ultima_vez_cocinada")

    registro = {
        "fecha_consumo": fecha_consumo,
        "fecha_cocinado": fecha_cocinado or None,
        "momento": resultado.get("momento") or "comida",
        "receta_id": str((receta or {}).get("id"))
        if receta and receta.get("id")
        else None,
        "tipo_reparto": resultado.get("tipo_reparto") or "estandar_55_45",
        "descripcion": descripcion,
        "completado": True,
        "nutricion_gonzalo": gonzalo or None,
        "nutricion_marta": marta or None,
    }

    try:
        add_registro_comida(registro)
    except Exception as exc:
        return f"⚠️ No se pudo registrar la comida: {str(exc)[:200]}"

    if nutricion:
        nota = (
            f"✅ Check Comido registrado: {descripcion} "
            f"({fecha_consumo}, {registro['momento']})."
        )
    else:
        nota = (
            f"✅ Comida registrada sin nutrientes: {descripcion} "
            f"({fecha_consumo}, {registro['momento']})."
        )
    return nota


def _ejecutar_accion(resultado: dict, contexto: dict) -> str | None:
    intencion = resultado.get("intencion") or "consulta"
    if intencion == "consulta":
        return None

    if intencion == "anadir_lista_compra":
        return _ejecutar_lista_compra(resultado, contexto)

    if intencion not in {"consumir_inventario", "check_comido"}:
        return None

    inventario = contexto.get("inventario") or []
    objetivo = str(resultado.get("objetivo_inventario") or "").strip()
    item = _buscar_item(objetivo, inventario)

    try:
        recetas = get_recetas()
    except Exception:
        recetas = []

    receta = _buscar_receta(resultado.get("receta_titulo") or objetivo, recetas)
    if not receta and item:
        receta = _buscar_receta(str(item.get("nombre") or ""), recetas)

    if not item and not receta:
        return (
            f"⚠️ No encuentro «{objetivo}» en el inventario ni en el recetario. "
            "No he modificado nada."
        )

    cantidad = resultado.get("cantidad_consumida")
    unidad = resultado.get("unidad_consumida")
    texto_consumo = _texto_consumo(cantidad, unidad)

    if item:
        try:
            detalle, factor = _consumir_item(item, cantidad, unidad)
        except Exception as exc:
            return f"⚠️ No se pudo actualizar el inventario: {str(exc)[:200]}"

        if intencion == "check_comido":
            nota = _registrar_check_comido(
                resultado, item, receta, texto_consumo, factor
            )
            return f"{nota} Inventario de «{item.get('nombre')}»: {detalle}."

        return (
            f"✅ Inventario actualizado: «{item.get('nombre')}» "
            f"({texto_consumo}). {detalle.capitalize()}."
        )

    if intencion == "check_comido":
        nota = _registrar_check_comido(
            resultado, None, receta, texto_consumo, 1.0
        )
        return f"{nota} No había táper de «{receta.get('titulo')}» en el inventario."

    return (
        f"⚠️ «{objetivo}» no está en el inventario como alimento o táper, "
        "así que no he descontado nada."
    )


def _procesar_entrada(texto: str | None = None, audio=None) -> None:
    if not ai_engine.motor_contextual_disponible():
        st.error("Configura GEMINI_API_KEY para usar el asistente.")
        return

    audio_bytes = audio.getvalue() if audio is not None else None
    mime_type = getattr(audio, "type", None) if audio is not None else None

    with st.spinner("Escuchando, consultando la despensa y el perfil clínico..."):
        try:
            contexto = ai_engine.construir_contexto_vivo()
            resultado = ai_engine.interpretar_asistente(
                texto=texto,
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                historial_conversacion=st.session_state["chat_contextual"],
                contexto=contexto,
            )
            nota_accion = _ejecutar_accion(resultado, contexto)
        except Exception as exc:
            _mostrar_error(exc)
            return

    entrada = str(resultado.get("transcripcion") or texto or "").strip()
    if audio is not None and not entrada:
        entrada = "🎤 Audio (sin transcripción)"
    elif audio is not None:
        entrada = f"🎤 {entrada}"
    if not entrada:
        entrada = "Consulta"

    contenido = str(resultado.get("respuesta") or "").strip()
    if nota_accion:
        contenido = f"{contenido}\n\n{nota_accion}".strip()

    st.session_state["chat_contextual"].append({"role": "user", "content": entrada})
    st.session_state["chat_contextual"].append(
        {"role": "assistant", "content": contenido}
    )
    st.session_state["_ultimo_contexto_motor"] = contexto["texto"]
    st.session_state["_ultima_intencion_asistente"] = resultado.get("intencion")
    st.rerun()


def render():
    st.header("🎙️ Asistente por Voz y Memoria")
    st.caption(
        "Habla o escribe: pide recetas, apunta a la compra, pregunta qué día "
        "cocinaste algo o registra lo que ya os habéis comido."
    )

    motor_listo = ai_engine.motor_contextual_disponible()
    if not motor_listo:
        st.warning(
            "Falta la GEMINI_API_KEY o el perfil clínico no está accesible. "
            "El asistente no puede responder todavía."
        )

    with st.expander("💡 Ejemplos de lo que puedes pedir", expanded=False):
        st.markdown(
            "- *¿Qué ceno hoy antirreflujo con lo que hay en la nevera?*\n"
            "- *¿Qué día cocinamos las lentejas que están en la nevera?*\n"
            "- *Apúntame en la lista de la compra café, aguacates y bolsas de basura.*\n"
            "- *El táper de lentejas ya nos lo hemos comido.*\n"
            "- *Registra que hemos comido pollo con arroz al mediodía.*"
        )

    if "chat_contextual" not in st.session_state:
        st.session_state["chat_contextual"] = []

    for turno in st.session_state["chat_contextual"]:
        with st.chat_message(turno["role"]):
            st.markdown(turno["content"])

    with st.expander("🎤 Hablar en vez de escribir", expanded=False):
        audio = st.audio_input("Graba tu consulta", key="asistente_audio")
        if st.button("Enviar audio", width="stretch", key="asistente_enviar_audio"):
            if audio is None:
                st.warning("Graba primero un audio.")
            elif not motor_listo:
                st.error("Configura GEMINI_API_KEY para usar el asistente.")
            else:
                _procesar_entrada(audio=audio)

    pregunta = st.chat_input(
        "Escribe tu consulta o pide una acción...",
        disabled=not motor_listo,
    )
    if pregunta:
        _procesar_entrada(texto=pregunta)

    if st.session_state["chat_contextual"]:
        if st.button("Borrar conversación", key="asistente_borrar"):
            st.session_state["chat_contextual"] = []
            st.session_state.pop("_ultimo_contexto_motor", None)
            st.session_state.pop("_ultima_intencion_asistente", None)
            st.rerun()

    if st.session_state.get("_ultimo_contexto_motor"):
        with st.expander("Ver contexto vivo enviado a la IA"):
            st.code(st.session_state["_ultimo_contexto_motor"], language=None)
