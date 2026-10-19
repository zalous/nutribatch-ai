import streamlit as st
from database import test_connection
from views import (
    p1_plan_y_compra,
    p2_cocinar_hoy,
    p3_asistente_voz,
    p4_salud_nutri,
)

# Configuración de página adaptada a móviles
st.set_page_config(
    page_title="NutriBatch AI",
    page_icon="🥗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Estilo personalizado para mejorar la visualización en teléfonos móviles
st.markdown(
    """
    <style>
    /* Ocultar barra superior por defecto para ganar espacio en móvil */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    /* Estilizar radio botones horizontales como barra de navegación móvil */
    div[role="radiogroup"] {
        display: flex;
        justify-content: space-around;
        background-color: #F0F4F1;
        padding: 6px;
        border-radius: 12px;
        margin-bottom: 1.2rem;
    }
    div[role="radiogroup"] > label {
        margin: 0 !important;
        padding: 4px 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cabecera principal
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🥗 NutriBatch AI")
with col_status:
    # Verificación de conexión en tiempo real
    if test_connection():
        st.success("🟢 Online")
    else:
        st.error("🔴 Offline")

# Navegación móvil entre las 4 pantallas
pantallas = {
    "🛒 Compra": p1_plan_y_compra.render,
    "🍳 Cocina": p2_cocinar_hoy.render,
    "🎙️ Voz": p3_asistente_voz.render,
    "📊 Salud": p4_salud_nutri.render,
}

seleccion = st.radio(
    "Navegación",
    options=list(pantallas.keys()),
    horizontal=True,
    label_visibility="collapsed",
)

# Renderizado de la pantalla activa
pantallas[seleccion]()
