import os
import unicodedata
from datetime import date

import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    """Obtiene o reutiliza la conexión autenticada a Supabase."""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "Faltan las credenciales de Supabase. Configura SUPABASE_URL y SUPABASE_KEY en .streamlit/secrets.toml"
        )

    return create_client(url, key)


def test_connection() -> bool:
    """Verifica que la conexión a Supabase y las tablas responden correctamente."""
    try:
        supabase = get_supabase_client()
        response = supabase.table("inventario").select("id").limit(1).execute()
        return True
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return False


# -----------------------------------------------------------------------------
# Funciones de Inventario
# -----------------------------------------------------------------------------
def get_inventario(ubicacion: str = None):
    """Obtiene los elementos del inventario, opcionalmente filtrados por ubicación."""
    supabase = get_supabase_client()
    query = supabase.table("inventario").select("*")
    if ubicacion:
        query = query.eq("ubicacion", ubicacion)
    response = query.order("fecha_entrada", desc=True).execute()
    return response.data or []


def add_item_inventario(item_data: dict):
    """Añade un nuevo alimento al inventario."""
    supabase = get_supabase_client()
    response = supabase.table("inventario").insert(item_data).execute()
    return response.data


def delete_item_inventario(item_id: str):
    """Elimina un alimento del inventario por su ID."""
    supabase = get_supabase_client()
    response = supabase.table("inventario").delete().eq("id", item_id).execute()
    return response.data


def delete_items_inventario(item_ids: list[str]) -> int:
    """Elimina varios alimentos del inventario de una sola vez. Devuelve cuántos borró."""
    ids = [str(i) for i in (item_ids or []) if i]
    if not ids:
        return 0
    supabase = get_supabase_client()
    response = supabase.table("inventario").delete().in_("id", ids).execute()
    return len(response.data or [])


def delete_all_inventario(ubicacion: str | None = None) -> int:
    """
    Vacía el inventario completo o solo una ubicación (nevera, congelador,
    despensa, batch_cocinado). Devuelve cuántos productos se borraron.
    """
    supabase = get_supabase_client()
    query = supabase.table("inventario").delete()
    if ubicacion:
        query = query.eq("ubicacion", ubicacion)
    else:
        # PostgREST exige un filtro explícito para permitir un DELETE masivo.
        query = query.neq("id", "00000000-0000-0000-0000-000000000000")
    response = query.execute()
    return len(response.data or [])


def update_item_inventario(item_id: str, update_data: dict):
    """Actualiza datos de un ítem del inventario."""
    supabase = get_supabase_client()
    response = (
        supabase.table("inventario")
        .update(update_data)
        .eq("id", item_id)
        .execute()
    )
    return response.data


# -----------------------------------------------------------------------------
# Funciones de Lista de la Compra
# -----------------------------------------------------------------------------
def get_lista_compra(comprado: bool = False):
    """Obtiene los ítems pendientes o comprados de la lista de la compra."""
    supabase = get_supabase_client()
    response = (
        supabase.table("lista_compra")
        .select("*")
        .eq("comprado", comprado)
        .order("fecha_anadido", desc=True)
        .execute()
    )
    return response.data or []


def add_item_lista_compra(item_data: dict):
    """Añade un ítem a la lista de la compra."""
    supabase = get_supabase_client()
    response = supabase.table("lista_compra").insert(item_data).execute()
    return response.data


def marcar_item_lista_compra(item_id: str, comprado: bool = True):
    """Marca o desmarca un ítem de la lista de la compra como comprado."""
    supabase = get_supabase_client()
    response = (
        supabase.table("lista_compra")
        .update({"comprado": comprado})
        .eq("id", item_id)
        .execute()
    )
    return response.data


def delete_item_lista_compra(item_id: str):
    """Elimina un ítem de la lista de la compra."""
    supabase = get_supabase_client()
    response = supabase.table("lista_compra").delete().eq("id", item_id).execute()
    return response.data


def delete_items_lista_compra(item_ids: list[str]) -> int:
    """Elimina varios ítems de la lista de la compra. Devuelve cuántos borró."""
    ids = [str(i) for i in (item_ids or []) if i]
    if not ids:
        return 0
    supabase = get_supabase_client()
    response = supabase.table("lista_compra").delete().in_("id", ids).execute()
    return len(response.data or [])


def delete_all_lista_compra(comprado: bool | None = None) -> int:
    """
    Vacía la lista de la compra completa o solo los pendientes/comprados.
    Devuelve cuántos ítems se borraron.
    """
    supabase = get_supabase_client()
    query = supabase.table("lista_compra").delete()
    if comprado is None:
        # PostgREST exige un filtro explícito para permitir un DELETE masivo.
        query = query.neq("id", "00000000-0000-0000-0000-000000000000")
    else:
        query = query.eq("comprado", comprado)
    response = query.execute()
    return len(response.data or [])


# -----------------------------------------------------------------------------
# Funciones de Diccionario de Tickets
# -----------------------------------------------------------------------------
def get_diccionario_tickets():
    """Obtiene la memoria guardada de productos de ticket."""
    supabase = get_supabase_client()
    response = supabase.table("diccionario_tickets").select("*").execute()
    return response.data or []


def upsert_diccionario_ticket(ticket_data: dict):
    """Guarda o actualiza un producto en el diccionario de tickets."""
    supabase = get_supabase_client()
    response = (
        supabase.table("diccionario_tickets")
        .upsert(ticket_data, on_conflict="texto_ticket")
        .execute()
    )
    return response.data


# -----------------------------------------------------------------------------
# Procesamiento automático de Tickets
# -----------------------------------------------------------------------------
def _normalizar_texto(texto: str) -> str:
    """Minúsculas, sin acentos y sin signos, para cruzar nombres de productos."""
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


def _a_bool(valor, defecto: bool = False) -> bool:
    """Convierte valores de IA, pandas o texto a booleano de forma segura."""
    if valor is None:
        return defecto
    try:
        if isinstance(valor, float) and valor != valor:
            return defecto
    except Exception:
        pass
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "1", "si", "sí", "yes")
    return bool(valor)


def _a_float(valor):
    """Convierte a float tolerando None, NaN y textos tipo '600 g'."""
    if valor is None:
        return None
    try:
        if isinstance(valor, float) and valor != valor:
            return None
        return float(str(valor).replace(",", ".").replace("g", "").strip())
    except Exception:
        return None


def _coincide_producto(nombre_a: str, nombre_b: str) -> bool:
    """Cruce por palabras significativas: evita que 'sal' tache 'salmón'."""
    a = _normalizar_texto(nombre_a)
    b = _normalizar_texto(nombre_b)
    if not a or not b:
        return False
    if a == b:
        return True

    vacias = {
        "de", "del", "la", "el", "los", "las", "y", "con", "al", "en",
        "un", "una", "unos", "unas", "para", "por",
    }
    tokens_a = {t for t in a.split() if t not in vacias}
    tokens_b = {t for t in b.split() if t not in vacias}
    if not tokens_a or not tokens_b:
        return False
    return tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a)


def procesar_y_guardar_ticket_items(items_ticket: list) -> dict:
    """
    Recibe la lista de dicts ya revisada y filtrada por el usuario en la interfaz:
    [
      {
        "texto_ticket": "CONTRAMUSLO POLLO BANDEJA",
        "nombre_limpio": "Contramuslo de pollo",
        "es_alimentacion": True,
        "supermercado": "Mercadona",
        "cantidad_aprox": "1 bandeja (600g)",
        "gramos_habituales": 600,
        "es_indivisible": False,
        "ubicacion_defecto": "nevera"
      },
      ...
    ]
    1. Guarda/actualiza en diccionario_tickets.
    2. Inserta en inventario si es_alimentacion == True (omite limpieza/hogar).
    3. Marca como comprados en lista_compra si hay coincidencias.
    """
    get_supabase_client()
    agregados_inventario = 0
    ignorados_hogar = 0
    tachados_lista = 0
    guardados_diccionario = 0

    fecha_compra = st.session_state.get("fecha_compra_ticket") or date.today().isoformat()

    # Cargar lista de la compra pendiente para cruzar
    lista_pendiente = list(get_lista_compra(comprado=False))

    for item in items_ticket or []:
        texto_orig = str(
            item.get("texto_ticket") or item.get("nombre_limpio") or ""
        ).strip()
        nombre_l = str(item.get("nombre_limpio") or texto_orig).strip()
        if not nombre_l:
            continue

        es_alim = _a_bool(item.get("es_alimentacion"), True)
        ubicacion = str(item.get("ubicacion_defecto") or "").strip().lower()
        if not es_alim or ubicacion == "hogar_no_inventariar":
            es_alim = False
            ubicacion = "hogar_no_inventariar"
        elif ubicacion not in ("nevera", "congelador", "despensa"):
            ubicacion = "despensa"

        gramos = _a_float(item.get("gramos_habituales"))
        if gramos is not None and gramos <= 0:
            gramos = None
        indivisible = _a_bool(item.get("es_indivisible"), False)
        cantidad = str(item.get("cantidad_aprox") or "").strip() or "1 unidad"
        supermercado = str(item.get("supermercado") or "").strip() or "General"

        # 1. Guardar en diccionario_tickets
        try:
            upsert_diccionario_ticket(
                {
                    "texto_ticket": texto_orig or nombre_l,
                    "nombre_limpio": nombre_l,
                    "es_alimentacion": es_alim,
                    "supermercado": supermercado,
                    "gramos_habituales": gramos,
                    "es_indivisible": indivisible,
                    "ubicacion_defecto": ubicacion,
                }
            )
            guardados_diccionario += 1
        except Exception:
            pass

        # 2. Si es alimentación, agregar a inventario
        if es_alim:
            try:
                add_item_inventario(
                    {
                        "nombre": nombre_l,
                        "ubicacion": ubicacion,
                        "cantidad_aprox": cantidad,
                        "gramos_estimados": gramos,
                        "es_indivisible": indivisible,
                        "fecha_entrada": fecha_compra,
                    }
                )
                agregados_inventario += 1
            except Exception:
                pass
        else:
            ignorados_hogar += 1

        # 3. Cruzar con lista_compra para tachar (cada ítem solo se tacha una vez)
        for item_lc in list(lista_pendiente):
            if _coincide_producto(nombre_l, item_lc.get("item", "")):
                try:
                    marcar_item_lista_compra(item_lc["id"], comprado=True)
                    tachados_lista += 1
                    lista_pendiente.remove(item_lc)
                except Exception:
                    pass

    return {
        "inventario": agregados_inventario,
        "hogar_omitido": ignorados_hogar,
        "lista_tachada": tachados_lista,
        "diccionario": guardados_diccionario,
    }


# -----------------------------------------------------------------------------
# Funciones de Recetas y Registro de Comidas
# -----------------------------------------------------------------------------
def get_recetas(aprobadas_solamente: bool = False):
    """Obtiene las recetas almacenadas."""
    supabase = get_supabase_client()
    query = supabase.table("recetas").select("*")
    if aprobadas_solamente:
        query = query.eq("aprobada", True)
    response = query.order("titulo").execute()
    return response.data or []


def add_receta(receta_data: dict):
    """Añade una nueva receta al catálogo."""
    supabase = get_supabase_client()
    response = supabase.table("recetas").insert(receta_data).execute()
    return response.data


def update_receta(receta_id: str, update_data: dict):
    """Actualiza los datos de una receta existente."""
    supabase = get_supabase_client()
    response = (
        supabase.table("recetas")
        .update(update_data)
        .eq("id", receta_id)
        .execute()
    )
    return response.data


def delete_receta(receta_id: str):
    """Elimina una receta del catálogo por su ID."""
    supabase = get_supabase_client()
    response = supabase.table("recetas").delete().eq("id", receta_id).execute()
    return response.data


def get_registro_comidas_fecha(fecha: str):
    """Obtiene el registro nutricional y de comidas para una fecha concreta (YYYY-MM-DD)."""
    supabase = get_supabase_client()
    response = (
        supabase.table("registro_comidas")
        .select("*")
        .eq("fecha_consumo", fecha)
        .order("created_at")
        .execute()
    )
    return response.data or []


def get_registro_comidas_recientes(limite: int = 25):
    """Obtiene las últimas comidas registradas, de la más reciente a la más antigua."""
    supabase = get_supabase_client()
    try:
        cantidad = max(1, int(limite))
    except (TypeError, ValueError):
        cantidad = 25
    response = (
        supabase.table("registro_comidas")
        .select("*")
        .order("fecha_consumo", desc=True)
        .order("created_at", desc=True)
        .limit(cantidad)
        .execute()
    )
    return response.data or []
