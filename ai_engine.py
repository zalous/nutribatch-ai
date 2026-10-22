import json
import os
import streamlit as st
from pydantic import BaseModel, Field


class ItemTicket(BaseModel):
    texto_ticket: str = Field(description="Nombre tal como aparece impreso en el ticket")
    nombre_limpio: str = Field(description="Nombre claro y legible del alimento o producto")
    es_alimentacion: bool = Field(description="True si es comida/bebida, False si es producto de limpieza, basura o higiene")
    supermercado: str = Field(default="General", description="Nombre del supermercado: Mercadona, Lidl, Consum, Dia...")
    cantidad_aprox: str = Field(default="1 unidad", description="Ejemplo: '1 bandeja (600g)', '6 unidades', '1 botella'")
    gramos_habituales: float | None = Field(default=None, description="Estimación del peso neto total en gramos si aplica")
    es_indivisible: bool = Field(default=False, description="True si es una pieza entera de pescado o alimento no fraccionable")
    ubicacion_defecto: str = Field(default="despensa", description="Ubicaciones: 'nevera', 'congelador', 'despensa', 'hogar_no_inventariar'")


class ResultadoTicket(BaseModel):
    supermercado: str
    fecha_compra: str
    items: list[ItemTicket]


SYSTEM_PROMPT_TICKETS = """
Eres un experto lector de tickets de supermercados españoles (Mercadona, Lidl, Consum, Dia, Carrefour...).
Tu objetivo es analizar la imagen, PDF o texto del ticket e identificar todos los productos comprados.

Instrucciones estrictas:
1. **Diferenciar Comida vs Hogar:**
   - Si el producto es de limpieza (detergente, lejía), papelería, bolsas de basura, servilletas, higiene -> `es_alimentacion = False` y `ubicacion_defecto = 'hogar_no_inventariar'`.
   - Si es alimento o bebida -> `es_alimentacion = True`.
2. **Asignar Ubicación Lógica:**
   - Carne fresca, pescado fresco, lácteos, verduras frescas -> `ubicacion_defecto = 'nevera'`.
   - Ultracongelados, helados, pescado/carne congelada -> `ubicacion_defecto = 'congelador'`.
   - Conservas, legumbres secas, arroz, aceite, pasta, huevos, especias -> `ubicacion_defecto = 'despensa'`.
3. **Pescados Enteros / Indivisibles:**
   - Si se trata de piezas enteras de pescado (ej. Dorada, Lubina) o un pollo entero -> `es_indivisible = True`.
"""


def procesar_ticket_con_ia(file_upload=None, texto_raw: str = None) -> list[dict]:
    """
    Procesa un ticket (Imagen, PDF o Texto) usando Gemini 2.5 Flash o un analizador de reglas estructurado.
    Devuelve una lista de diccionarios con los productos clasificados.
    """
    gemini_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)

            contents = [SYSTEM_PROMPT_TICKETS]

            if file_upload is not None:
                bytes_data = file_upload.getvalue()
                mime_type = file_upload.type
                if mime_type == "application/pdf":
                    contents.append(
                        types.Part.from_bytes(data=bytes_data, mime_type="application/pdf")
                    )
                else:
                    contents.append(
                        types.Part.from_bytes(data=bytes_data, mime_type=mime_type or "image/jpeg")
                    )
            elif texto_raw:
                contents.append(f"Texto del ticket:\n{texto_raw}")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResultadoTicket,
                    temperature=0.1,
                ),
            )

            res_json = json.loads(response.text)
            return [item for item in res_json.get("items", [])]

        except Exception as e:
            st.warning(f"Aviso en la llamada a Gemini: {e}. Usando regla alternativa de procesamiento.")

    # Regla fallback / demostrativa si no hay GEMINI_API_KEY configurada
    return _procesar_ticket_fallback(texto_raw or (file_upload.name if file_upload else ""))


def _procesar_ticket_fallback(origen_texto: str) -> list[dict]:
    """Fallback inteligente para procesar entradas en texto plano o CSV simulados."""
    lineas = [l.strip() for l in origen_texto.split("\n") if l.strip()]
    items = []

    palabras_hogar = ["papel", "bolsa", "detergente", "fregona", "servilleta", "champú", "jabón", "suavizante"]
    palabras_nevera = ["pollo", "pavo", "ternera", "dorada", "salmón", "yogur", "leche", "queso", "jamón", "huevos", "tomate"]
    palabras_congelador = ["congelado", "helado", "pizzas", "ultracongelado"]

    for linea in lineas:
        if len(linea) < 2 or "total" in linea.lower() or "tarjeta" in linea.lower():
            continue

        l_lower = linea.lower()
        es_alim = not any(h in l_lower for h in palabras_hogar)

        if not es_alim:
            ubicacion = "hogar_no_inventariar"
        elif any(c in l_lower for c in palabras_congelador):
            ubicacion = "congelador"
        elif any(n in l_lower for n in palabras_nevera):
            ubicacion = "nevera"
        else:
            ubicacion = "despensa"

        es_indiv = "dorada" in l_lower or "lubina" in l_lower or "pollo entero" in l_lower

        items.append({
            "texto_ticket": linea,
            "nombre_limpio": linea.title(),
            "es_alimentacion": es_alim,
            "supermercado": "Mercadona/Súper",
            "cantidad_aprox": "1 unidad",
            "gramos_habituales": 500.0 if es_alim else None,
            "es_indivisible": es_indiv,
            "ubicacion_defecto": ubicacion,
        })

    return items
