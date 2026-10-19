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
        # Prueba una consulta ligera sobre inventario
        response = supabase.table("inventario").select("id").limit(1).execute()
        return True
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return False


# -----------------------------------------------------------------------------
# Funciones básicas de Inventario
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


# -----------------------------------------------------------------------------
# Funciones básicas de Lista de la Compra
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


# -----------------------------------------------------------------------------
# Funciones básicas de Recetas
# -----------------------------------------------------------------------------
def get_recetas(aprobadas_solamente: bool = False):
    """Obtiene las recetas almacenadas."""
    supabase = get_supabase_client()
    query = supabase.table("recetas").select("*")
    if aprobadas_solamente:
        query = query.eq("aprobada", True)
    response = query.order("titulo").execute()
    return response.data or []


# -----------------------------------------------------------------------------
# Funciones básicas de Registro de Comidas
# -----------------------------------------------------------------------------
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
