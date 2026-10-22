import os
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
def procesar_y_guardar_ticket_items(items_ticket: list) -> dict:
    """
    Recibe una lista de dicts procesados por la IA:
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
    supabase = get_supabase_client()
    agregados_inventario = 0
    ignorados_hogar = 0
    tachados_lista = 0

    # Cargar lista de la compra pendiente para cruzar
    lista_pendiente = get_lista_compra(comprado=False)

    for item in items_ticket:
        texto_orig = item.get("texto_ticket", "").strip()
        nombre_l = item.get("nombre_limpio", texto_orig).strip()
        es_alim = item.get("es_alimentacion", True)
        ubicacion = item.get("ubicacion_defecto", "despensa")

        # 1. Guardar en diccionario_tickets
        try:
            upsert_diccionario_ticket({
                "texto_ticket": texto_orig,
                "nombre_limpio": nombre_l,
                "es_alimentacion": es_alim,
                "supermercado": item.get("supermercado", "General"),
                "gramos_habituales": item.get("gramos_habituales"),
                "es_indivisible": item.get("es_indivisible", False),
                "ubicacion_defecto": ubicacion,
            })
        except Exception as e:
            pass

        # 2. Si es alimentación, agregar a inventario
        if es_alim and ubicacion != "hogar_no_inventariar":
            try:
                add_item_inventario({
                    "nombre": nombre_l,
                    "ubicacion": ubicacion if ubicacion in ["nevera", "congelador", "despensa"] else "despensa",
                    "cantidad_aprox": item.get("cantidad_aprox", "1 unidad"),
                    "gramos_estimados": item.get("gramos_habituales"),
                    "es_indivisible": item.get("es_indivisible", False),
                    "fecha_entrada": str(st.session_state.get("fecha_compra_ticket") or "2026-10-21"),
                })
                agregados_inventario += 1
            except Exception as e:
                pass
        else:
            ignorados_hogar += 1

        # 3. Cruzar con lista_compra para tachar
        for item_lc in lista_pendiente:
            item_lc_nombre = item_lc["item"].lower()
            if nombre_l.lower() in item_lc_nombre or item_lc_nombre in nombre_l.lower():
                try:
                    marcar_item_lista_compra(item_lc["id"], comprado=True)
                    tachados_lista += 1
                except Exception as e:
                    pass

    return {
        "inventario": agregados_inventario,
        "hogar_omitido": ignorados_hogar,
        "lista_tachada": tachados_lista,
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
