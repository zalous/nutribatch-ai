import io
import json
import os
import re
import time
import unicodedata

import streamlit as st
from pydantic import BaseModel, Field


# Modelos vigentes de Google (se prueban en orden hasta que uno responda).
# gemini-2.5-flash ya no está disponible para claves nuevas (octubre 2026).
MODELOS_IA = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


# =============================================================================
# MODELOS ESTRUCTURADOS (para Gemini)
# =============================================================================
class ItemTicket(BaseModel):
    texto_ticket: str = Field(description="Nombre tal como aparece impreso en el ticket")
    nombre_limpio: str = Field(description="Nombre claro y legible del alimento o producto")
    es_alimentacion: bool = Field(description="True si es comida/bebida, False si es limpieza, hogar o higiene")
    supermercado: str = Field(default="General", description="Mercadona, Lidl, Consum, Dia, Carrefour...")
    cantidad_aprox: str = Field(default="1 unidad", description="Ej: '1 bandeja (600g)', '6 unidades'")
    gramos_habituales: float | None = Field(
        default=None,
        description="Peso neto total en gramos SOLO si el ticket lo indica de forma explícita (ej. '0,650 kg' o '600 g'). Si no aparece, null: nunca lo estimes ni lo inventes.",
    )
    es_indivisible: bool = Field(default=False, description="True si es pieza entera no fraccionable (dorada, lubina, pollo entero)")
    ubicacion_defecto: str = Field(default="despensa", description="'nevera', 'congelador', 'despensa' o 'hogar_no_inventariar'")


class ResultadoTicket(BaseModel):
    supermercado: str
    fecha_compra: str
    items: list[ItemTicket]


SYSTEM_PROMPT_TICKETS = """
Eres un experto lector de tickets de supermercados españoles (Mercadona, Lidl, Consum, Dia, Carrefour, Alcampo...).
Analiza la imagen, PDF o texto del ticket y extrae SOLO los productos realmente comprados.

Reglas estrictas:
1. IGNORA por completo: nombre y dirección del supermercado, CIF/NIF, teléfono, número de ticket/factura,
   cajero, fecha/hora, líneas de IVA, subtotales, TOTAL, forma de pago (tarjeta/efectivo), descuentos,
   puntos de fidelidad, mensajes de gracias y cualquier dato fiscal o publicitario.
2. NO inventes productos. Si una línea no es un artículo comprado, no la incluyas.
3. Las líneas de peso/precio de continuación (ej. "0,650 kg x 5,20 3,38") pertenecen al producto
   de la línea anterior: únelas a ese producto y NUNCA las devuelvas como un producto aparte.
4. Si una línea es un descuento o devolución (importe negativo), no la incluyas como producto.
5. Clasifica cada producto:
   - Limpieza, papelería, higiene, bolsas de basura, servilletas -> es_alimentacion=False y ubicacion_defecto='hogar_no_inventariar'.
   - Carne/pescado fresco, lácteos, verduras frescas -> 'nevera'.
   - Congelados y helados -> 'congelador'.
   - Conservas, legumbres secas, arroz, pasta, aceite, huevos, especias, bebidas -> 'despensa'.
6. Marca es_indivisible=True para piezas enteras (dorada, lubina, pollo entero).
7. Usa el nombre limpio y legible (sin códigos ni abreviaturas raras) en nombre_limpio.
8. NUNCA inventes ni estimes el peso: rellena gramos_habituales SOLO si el ticket indica
   el peso de forma explícita (ej. "0,650 kg", "600 g", "1,5 L"). Si el ticket no lo dice,
   deja gramos_habituales en null, aunque conozcas el producto o su precio.
"""


# =============================================================================
# NORMALIZACIÓN Y DICCIONARIOS
# =============================================================================
def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos para comparar palabras clave."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


PALABRAS_NO_PRODUCTO = [
    "s.a.", "s.l.", "s.a", "s.l", "cif", "nif", "nie", "telf", "telefono", "fax",
    "calle", "avda", "avenida", "plaza", "poligono", "carretera", "ctra", "paseo",
    "factura", "ticket", "simplificada", "recibo", "justificante", "caja", "cajero",
    "turno", "operador", "fecha", "hora", "cliente", "socio", "puntos", "fidelidad",
    "total", "subtotal", "iva", "base imponible", "importe", "cambio", "efectivo",
    "tarjeta", "visa", "mastercard", "descuento", "ahorro", "devolucion", "entrega",
    "www.", "http", ".com", ".es", "gracias por su compra", "muchas gracias",
    "articulo", "unidades", "precio", "importe total", "a pagar", "pendiente",
]

# Palabras que confirman que la línea es un producto de alimentación
PALABRAS_ALIMENTO = [
    "pollo", "pavo", "ternera", "cerdo", "cordero", "conejo", "jamon", "lomo",
    "salmon", "dorada", "lubina", "merluza", "atun", "sardina", "bacalao", "gamba",
    "leche", "yogur", "yogurt", "queso", "huevo", "huevos", "mantequilla", "nata",
    "pan", "harina", "arroz", "pasta", "macarron", "espagueti", "lenteja", "garbanzo",
    "guisante", "alubia", "aceite", "vinagre", "sal", "azucar", "miel", "cafe", "te",
    "tomate", "cebolla", "ajo", "pimiento", "zanahoria", "calabacin", "berenjena",
    "patata", "boniato", "brocoli", "coliflor", "espinaca", "lechuga", "pepino",
    "manzana", "platano", "naranja", "limon", "kiwi", "fresa", "pera", "uva",
    "aguacate", "fruto seco", "nuez", "almendra", "avena", "cereal", "legumbre",
    "agua", "zumo", "vino", "cerveza", "refresco", "conserva", "tomate frito",
    "aceituna", "especia", "pimienta", "oregano", "canela", "cacao", "chocolate",
]

# Productos de hogar / limpieza / higiene
PALABRAS_HOGAR = [
    "papel", "servilleta", "bolsa basura", "bolsas basura", "detergente", "suavizante",
    "lejia", "fregona", "estropajo", "lavavajillas", "limpiador", "limpieza", "jabon",
    "champu", "gel", "desodorante", "pasta de dientes", "cepillo", "compresa",
    "panal", "toallita", "higienico", "film", "aluminio", "pilas", "bombilla",
    "ambientador", "insecticida", "guantes", "basura", "friegasuelos", "quitamanchas",
]

PALABRAS_CONGELADOR = ["congelado", "congelada", "ultracongelado", "helado", "pizza"]
PALABRAS_NEVERA = [
    "pollo", "pavo", "ternera", "cerdo", "cordero", "conejo", "jamon", "lomo",
    "salmon", "dorada", "lubina", "merluza", "atun", "sardina", "bacalao", "gamba",
    "leche", "yogur", "yogurt", "queso", "huevo", "huevos", "mantequilla", "nata",
    "tomate", "lechuga", "espinaca", "brocoli", "pepino", "zanahoria", "calabacin",
    "manzana", "platano", "naranja", "kiwi", "fresa", "pera", "uva", "aguacate",
]
PALABRAS_INDIVISIBLES = ["dorada", "lubina", "pollo entero", "merluza entera", "besugo", "rodaballo"]

# Precio al final de línea: 4,50 / 4.50 / 1.234,56 / 4,50 € / 4,50 EUR
RE_PRECIO_FINAL = re.compile(r"\s+(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*(?:€|eur|e)?\s*$", re.IGNORECASE)
RE_PRECIO_NEGATIVO = re.compile(r"-\s*\d+[.,]\d{2}\s*$")
RE_CANTIDAD_INICIAL = re.compile(r"^\s*(\d{1,3})\s*(?:x|ud|uds|unid|unidades)?\s+", re.IGNORECASE)
RE_PESO_INICIAL = re.compile(r"^\s*(\d+[.,]\d{2,3})\s*(kg|g|l|ml)\b", re.IGNORECASE)
RE_PESO_X_PRECIO = re.compile(r"\b\d+[.,]\d{2,3}\s*(?:kg|g|l|ml)\s*x\s*\d+[.,]\d{2}\b", re.IGNORECASE)
RE_PESO_EXPLICITO = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kg|kilos?|g|gr|gramos?|l|litros?|ml)\b",
    re.IGNORECASE,
)
RE_CODIGO_IVA = re.compile(r"\s+[A-Z]\s*$")
RE_SOLO_SIMBOLOS = re.compile(r"^[\W\d_]+$")
RE_HORA = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
RE_FECHA = re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b")
RE_DIRECCION = re.compile(
    r"^(?:c/|c\.|cl\.|calle|avda|av\.|avenida|plaza|pza|poligono|pol\.|ctra|carretera|"
    r"paseo|ronda|camino|urb\.|urbanizacion)(?:\s|$)",
    re.IGNORECASE,
)
RE_CODPOSTAL = re.compile(r"^\d{5}\b")


def _contiene_palabra(texto_norm: str, palabras: list[str]) -> bool:
    """Busca palabras clave respetando límites de palabra y plurales simples."""
    for palabra in palabras:
        patron = r"\b" + re.escape(palabra) + r"(?:e?s)?\b"
        if re.search(patron, texto_norm):
            return True
    return False


def _es_linea_no_producto(linea: str) -> bool:
    """Determina si una línea del ticket es metadato (cabecera, total, pago, etc.)."""
    if not linea or len(linea.strip()) < 3:
        return True
    if RE_SOLO_SIMBOLOS.match(linea.strip()):
        return True
    if RE_HORA.search(linea) and len(linea) < 30:
        return True
    if RE_FECHA.search(linea) and len(linea) < 25:
        return True

    limpia = linea.strip()
    if RE_DIRECCION.match(limpia) or RE_CODPOSTAL.match(limpia):
        return True

    norm = _normalizar(linea)
    if RE_PRECIO_NEGATIVO.search(linea):
        return True
    for palabra in PALABRAS_NO_PRODUCTO:
        if palabra in norm:
            return True

    letras = sum(1 for c in linea if c.isalpha())
    if letras < 3:
        return True
    return False


def _limpiar_nombre_producto(linea: str) -> tuple[str, str | None, float | None]:
    """
    Extrae (nombre_limpio, cantidad_aprox, gramos_estimados) de una línea de producto.
    """
    texto = linea.strip()

    gramos = None
    cantidad = "1 unidad"

    match_peso = RE_PESO_INICIAL.match(texto)
    if match_peso:
        valor = match_peso.group(1).replace(",", ".")
        unidad = match_peso.group(2).lower()
        try:
            num = float(valor)
            if unidad == "kg":
                gramos = num * 1000
            elif unidad == "g":
                gramos = num
            elif unidad in ("l", "ml"):
                gramos = num * 1000 if unidad == "l" else num
            cantidad = f"{match_peso.group(1)} {unidad}"
        except ValueError:
            pass
        texto = texto[match_peso.end():].strip()

    match_cant = RE_CANTIDAD_INICIAL.match(texto)
    if match_cant and not match_peso:
        try:
            n = int(match_cant.group(1))
            if 0 < n <= 99:
                cantidad = "1 unidad" if n == 1 else f"{n} unidades"
                texto = texto[match_cant.end():].strip()
        except ValueError:
            pass

    texto = RE_PESO_X_PRECIO.sub("", texto)
    texto = RE_PRECIO_FINAL.sub("", texto)
    texto = texto.strip(" .-*·|")

    if len(texto) > 3:
        texto = RE_CODIGO_IVA.sub("", texto).strip()

    nombre = " ".join(texto.split())
    if nombre.isupper() or nombre.islower():
        nombre = nombre.title()

    return nombre, cantidad, gramos


def _peso_explicito_en_item(item: dict) -> bool:
    """True solo si el ticket muestra un peso/volumen real; si no, los gramos sobran."""
    partes = (
        item.get("texto_ticket"),
        item.get("cantidad_aprox"),
        item.get("nombre_limpio"),
    )
    return any(RE_PESO_EXPLICITO.search(str(p)) for p in partes if p)


def _clasificar_producto(nombre: str) -> tuple[bool, str, bool]:
    """Devuelve (es_alimentacion, ubicacion_defecto, es_indivisible)."""
    norm = _normalizar(nombre)

    es_hogar = _contiene_palabra(norm, PALABRAS_HOGAR)
    es_alimento = _contiene_palabra(norm, PALABRAS_ALIMENTO)

    es_indivisible = _contiene_palabra(norm, PALABRAS_INDIVISIBLES)

    if es_hogar and not es_alimento:
        return False, "hogar_no_inventariar", False
    if es_hogar and es_alimento:
        # Ante la duda, prioriza el filtro de hogar si no hay verbo claro de comida
        return False, "hogar_no_inventariar", False
    if not es_alimento and not es_hogar:
        # Línea con letras y precio pero no reconocida: se asume alimento genérico
        return True, "despensa", es_indivisible
    if _contiene_palabra(norm, PALABRAS_CONGELADOR):
        return True, "congelador", es_indivisible
    if _contiene_palabra(norm, PALABRAS_NEVERA):
        return True, "nevera", es_indivisible
    return True, "despensa", es_indivisible


def detectar_supermercado(texto: str) -> str:
    norm = _normalizar(texto)
    for nombre in ["mercadona", "lidl", "consum", "dia", "carrefour", "alcampo", "eroski", "aldi", "hipercor", "mas", "supersol"]:
        if nombre in norm:
            return nombre.title()
    return "General"


# =============================================================================
# PARSER DE TEXTO / CSV
# =============================================================================
def parsear_texto_ticket(texto: str) -> list[dict]:
    """Analiza el texto plano de un ticket y devuelve los productos limpios."""
    if not texto or not texto.strip():
        return []

    supermercado = detectar_supermercado(texto)
    items: list[dict] = []
    lineas = texto.replace("\r", "\n").split("\n")

    modo_csv = ";" in texto and any(
        p in _normalizar(lineas[0]) for p in ["producto", "articulo", "descripcion", "nombre", "importe"]
    )

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        # Línea de peso que continúa al producto anterior: "0,650 kg x 5,20 3,38"
        match_peso_linea = RE_PESO_INICIAL.match(linea)
        if items and match_peso_linea and not any(c.isalpha() for c in linea[:2]):
            try:
                valor = float(match_peso_linea.group(1).replace(",", "."))
                unidad = match_peso_linea.group(2).lower()
                gramos_prev = valor * 1000 if unidad == "kg" else valor
                items[-1]["gramos_habituales"] = gramos_prev
                items[-1]["cantidad_aprox"] = f"{match_peso_linea.group(1)} {unidad}"
                continue
            except ValueError:
                pass

        if modo_csv:
            campos = [c.strip() for c in linea.split(";")]
            if len(campos) < 2:
                continue
            nombre_campo = next((c for c in campos if sum(ch.isalpha() for ch in c) >= 3), "")
            if not nombre_campo or _es_linea_no_producto(nombre_campo):
                continue
            if "producto" in _normalizar(nombre_campo) or "articulo" in _normalizar(nombre_campo):
                continue
            nombre, cantidad, gramos = _limpiar_nombre_producto(nombre_campo)
            texto_orig = linea
        else:
            if _es_linea_no_producto(linea):
                continue
            texto_orig = linea
            nombre, cantidad, gramos = _limpiar_nombre_producto(linea)

        if len(nombre) < 3 or sum(ch.isalpha() for ch in nombre) < 3:
            continue

        es_alim, ubicacion, indivisible = _clasificar_producto(nombre)

        items.append({
            "texto_ticket": texto_orig,
            "nombre_limpio": nombre,
            "es_alimentacion": es_alim,
            "supermercado": supermercado,
            "cantidad_aprox": cantidad,
            "gramos_habituales": gramos,
            "es_indivisible": indivisible,
            "ubicacion_defecto": ubicacion,
        })

    return items


def _extraer_texto_pdf(file_upload) -> str:
    """Extrae el texto embebido de un PDF (tickets digitales)."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_upload.getvalue()))
        partes = []
        for pagina in reader.pages:
            try:
                partes.append(pagina.extract_text() or "")
            except Exception:
                continue
        return "\n".join(partes)
    except Exception:
        return ""


def tiene_gemini_key() -> bool:
    try:
        return bool(st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    except Exception:
        return bool(os.environ.get("GEMINI_API_KEY"))


def _get_gemini_key() -> str | None:
    try:
        return st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    except Exception:
        return os.environ.get("GEMINI_API_KEY")


def _modelos_agotados() -> set:
    """Modelos con cuota diaria agotada en esta sesión (no se vuelven a intentar)."""
    try:
        return set(st.session_state.get("_gemini_agotados", set()))
    except Exception:
        return set()


def _marcar_agotado(modelo: str) -> None:
    try:
        agotados = set(st.session_state.get("_gemini_agotados", set()))
        agotados.add(modelo)
        st.session_state["_gemini_agotados"] = agotados
    except Exception:
        pass


def _generar_con_fallback(client, contents, config):
    """Prueba los modelos en orden. La cuota diaria (429) no se reintenta: se salta al siguiente."""
    agotados = _modelos_agotados()
    errores = []
    for modelo in MODELOS_IA:
        if modelo in agotados:
            errores.append(f"{modelo}: cuota diaria agotada")
            continue
        try:
            return client.models.generate_content(
                model=modelo, contents=contents, config=config
            )
        except Exception as e:
            mensaje = str(e)
            if "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje:
                _marcar_agotado(modelo)
                errores.append(f"{modelo}: cuota diaria agotada")
                continue
            if "503" in mensaje or "UNAVAILABLE" in mensaje:
                time.sleep(1.5)
                try:
                    return client.models.generate_content(
                        model=modelo, contents=contents, config=config
                    )
                except Exception as e2:
                    errores.append(f"{modelo}: {str(e2)[:90]}")
                    continue
            errores.append(f"{modelo}: {mensaje[:90]}")
            continue
    raise RuntimeError("; ".join(errores) if errores else "Gemini no respondió")


def _procesar_con_gemini(payload_partes: list, texto_apoyo: str | None = None) -> list[dict] | None:
    """Llama a Gemini (visión/texto) y devuelve los ítems o None si falla."""
    gemini_key = _get_gemini_key()
    if not gemini_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)

        contents = [SYSTEM_PROMPT_TICKETS]
        contents.extend(payload_partes)
        if texto_apoyo:
            contents.append(f"Texto OCR/extraído de apoyo del mismo ticket:\n{texto_apoyo}")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResultadoTicket,
            temperature=0.0,
        )

        response = _generar_con_fallback(client, contents, config)

        data = json.loads(response.text)
        items = data.get("items", [])
        # Saneado: descarta ítems vacíos o sin nombre válido
        limpios = []
        for it in items:
            nombre = str(it.get("nombre_limpio") or it.get("texto_ticket") or "").strip()
            if len(nombre) < 3:
                continue
            it["nombre_limpio"] = nombre

            # Los gramos solo se conservan si el ticket los muestra de forma explícita.
            gramos = it.get("gramos_habituales")
            try:
                gramos = None if gramos is None else float(gramos)
            except (TypeError, ValueError):
                gramos = None
            if gramos is not None and (
                gramos <= 0 or not _peso_explicito_en_item(it)
            ):
                gramos = None
            it["gramos_habituales"] = gramos

            ubicacion = it.get("ubicacion_defecto", "despensa")
            if it.get("es_alimentacion") is False:
                it["ubicacion_defecto"] = "hogar_no_inventariar"
            elif ubicacion not in ("nevera", "congelador", "despensa"):
                it["ubicacion_defecto"] = "despensa"
            limpios.append(it)
        return limpios
    except Exception as e:
        st.warning(
            "No se pudo usar Gemini Vision (cuota diaria agotada o modelos saturados). "
            "Se intentará el analizador de texto local."
        )
        with st.expander("Detalle técnico"):
            st.code(str(e), language=None)
        return None


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================
def procesar_ticket_con_ia(file_upload=None, texto_raw: str = None) -> list[dict]:
    """
    Procesa un ticket (imagen, PDF o texto) y devuelve los productos clasificados.

    - Imagen: requiere GEMINI_API_KEY (Gemini Vision). Sin clave avisa y devuelve [].
    - PDF: usa Gemini si hay clave; si no, extrae el texto del PDF y lo parsea localmente.
    - Texto/CSV pegado: parser local robusto; si no detecta nada y hay clave, reintenta con Gemini.
    """
    # ---- Texto pegado: parser local determinista (gratis y fiable) ----
    if texto_raw and texto_raw.strip():
        items = parsear_texto_ticket(texto_raw)
        if items:
            return items
        if tiene_gemini_key():
            gemini = _procesar_con_gemini([f"Texto del ticket:\n{texto_raw}"])
            if gemini:
                return gemini
        st.warning(
            "No se han detectado productos en el texto pegado. Revisa que el ticket incluya "
            "líneas de producto con su precio o adjunta una foto/PDF."
        )
        return []

    if file_upload is None:
        return []

    mime_type = getattr(file_upload, "type", "") or ""
    es_pdf = mime_type == "application/pdf" or str(getattr(file_upload, "name", "")).lower().endswith(".pdf")

    # ---- PDF ----
    if es_pdf:
        texto_pdf = _extraer_texto_pdf(file_upload)
        if tiene_gemini_key():
            from google.genai import types

            partes = [types.Part.from_bytes(data=file_upload.getvalue(), mime_type="application/pdf")]
            gemini = _procesar_con_gemini(partes, texto_apoyo=texto_pdf[:8000] if texto_pdf else None)
            if gemini:
                return gemini
        if texto_pdf.strip():
            items = parsear_texto_ticket(texto_pdf)
            if items:
                return items
            st.warning("El PDF no contiene líneas de producto reconocibles. Prueba a subir una foto del ticket.")
            return []
        st.warning(
            "Este PDF parece escaneado (solo imagen). Para leerlo hace falta configurar la "
            "GEMINI_API_KEY del Paso 2.3."
        )
        return []

    # ---- Imagen ----
    if not tiene_gemini_key():
        st.error(
            "Para leer tickets en foto se necesita la API Key de Google Gemini (Paso 2.3). "
            "Mientras tanto, pega el texto del ticket o sube el PDF digital de la app del súper."
        )
        return []

    from google.genai import types

    partes = [types.Part.from_bytes(data=file_upload.getvalue(), mime_type=mime_type or "image/jpeg")]
    gemini = _procesar_con_gemini(partes)
    if gemini:
        return gemini

    st.error("No se pudo interpretar la imagen del ticket. Prueba con mejor luz y enfoque, o pega el texto.")
    return []
