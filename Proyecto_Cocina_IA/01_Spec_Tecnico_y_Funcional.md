---
documento: Spec Técnico y Funcional
version: 1.1
stack: Python + Streamlit Cloud + Supabase + Gemini 3.6 Flash
---
# Especificacion Tecnica y Funcional

## 1. Reglas de Oro para la IA Desarrolladora y para la IA de la App
1. **Cero código manual por parte del usuario:** El agente de código crea y edita todos los archivos completos. Prohibido truncar código.
2. **Arquitectura 100% Online, Gratis y Sin Servidor Propio:**
   - **Frontend y Backend:** P[[00_MOC_Dashboard.md]]ython (`streamlit`) alojado gratis en Streamlit Community Cloud.
   - **Base de Datos:** `supabase` (PostgreSQL en la nube, capa gratuita).
   - **Motor IA (Texto, Visión y Audio):** `google-genai` usando `gemini-3.6-flash` como modelo principal (con respaldo automático a `gemini-3.5-flash`, `gemini-3.7-flash` y `gemini-3.8-flash` ante saturación) y respuestas estructuradas (`pydantic`). Nota: `gemini-2.5-flash` ya no está disponible para claves nuevas desde octubre de 2026.
   - **Credenciales:** la `GEMINI_API_KEY` se guarda en `.streamlit/secrets.toml` (local) y en los Secrets de Streamlit Community Cloud (producción), nunca en GitHub.
3. **Cerebro IA Especializado (Inyección de Contexto Permanente):**
   - El módulo `ai_engine.py` debe cargar siempre como `system_instruction` las reglas médicas, de porciones y de alimentos de `02_Perfil_Clinico_y_Nutricional.md`.
   - Además, en cada consulta del usuario (por voz o botón), se le inyectará el contexto vivo de Supabase: qué hay en `inventario` (con sus fechas de cocinado), qué hay pendiente en `lista_compra` y cuándo se cocinaron los últimos platos en `registro_comidas`.
4. **Filosofía de Inventario, Lotes (Batch) y Fechas de Cocinado:**
   - **Sin básculas:** Cantidades lógicas o aproximadas (unidades, bandejas, tápers).
   - **Control de Fecha de Cocinado (`fecha_cocinado`):** Cada vez que se cocina un lote de Batch Cooking o una receta que se guarda, se registra exactamente qué día se cocinó. Así la app muestra cuántos días lleva hecho cada táper en la nevera/congelador y la IA puede responder preguntas como "¿Qué día cocinamos las lentejas o el pollo?".
   - **Lógica de Ollas y Raciones:** Las recetas grandes definen cuántas **comidas de pareja** salen de la olla entera (ej. 1 olla = 3 comidas para los dos). Al comer entre semana, se resta solo 1 comida de pareja del lote y se suman únicamente los nutrientes de esa toma individual (aprox. 55% Gonzalo / 45% Marta en guisos para cuadrar 1.700 kcal y 1.350 kcal, o 50/50 en unidades iguales).
   - **Regla de Indivisibles (Regla de la Dorada):** Alimentos que se gastan enteros en una comida nunca se fraccionan crudos.
   - **Segundo Cerebro en Lista de la Compra:** Permite apuntar tanto ingredientes de recetas como productos generales del súper o del hogar (papel, detergente, café, básicos) por texto o por voz. Al subir el ticket del súper, la IA tacha lo comprado de la lista pero solo mete en el `inventario` nutricional lo que sea comida.

---

## 2. Estructura de Archivos del Codigo
En la carpeta raíz del proyecto (fuera de la subcarpeta de Obsidian):
- `.streamlit/config.toml` (Diseño adaptado a pantallas de móvil)
- `.streamlit/secrets.toml` (Credenciales seguras: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`)
- `requirements.txt` (Librerías: `streamlit`, `supabase`, `google-genai`, `pydantic`, `pypdf`, `pillow`)
- `app.py` (Menú principal móvil y navegación entre las 4 pantallas)
- `database.py` (Conexión y consultas a Supabase)
- `ai_engine.py` (Cerebro IA con System Prompt clínico/batch, lector de tickets, fotos, voz y planificador)
- **Subcarpeta `views/`:**
  - `p1_plan_y_compra.py` (Planificador con IA, Recetas aprobadas, Lista de la Compra Unificada Comida+Hogar y Subida de Ticket)
  - `p2_cocinar_hoy.py` (Nevera/Congelador con fechas de cocinado, Check de cocinado/comido, Foto en encimera y Recetas de rescate Mié/Jue)
  - `p3_asistente_voz.py` (Consultor por Voz y Texto: pedir ideas de batch/cenas/desayunos, añadir a la lista de la compra o preguntar qué día se cocinó un plato)
  - `p4_salud_nutri.py` (Progreso diario Gonzalo vs Marta y Panel semanal de macros, vitaminas y minerales)

---

## 3. Esquema de Base de Datos (Supabase)

### Tabla 1: `inventario`
- `id` (UUID, Primary Key)
- `nombre` (Text) — Ej: "Pechuga de pollo", "Dorada", "Táper Lentejas con verduras".
- `ubicacion` (Text) — Valores: `nevera`, `congelador`, `despensa`, `batch_cocinado`.
- `cantidad_aprox` (Text) — Ej: "3 unidades", "1 bandeja", "2 comidas de pareja".
- `gramos_estimados` (Numeric) — Estimación interna de la IA.
- `es_indivisible` (Boolean) — `True` si se gasta entero en una comida.
- `nutricion_por_comida_pareja` (JSONB, opcional) — Para los ítems en `batch_cocinado`, guarda los nutrientes de 1 comida de pareja.
- `fecha_entrada` (Date) — Día en que se compró.
- `fecha_cocinado` (Date, opcional) — Día exacto en que se cocinó (clave para saber cuántos días lleva hecho un táper o receta en la nevera/congelador).

### Tabla 2: `diccionario_tickets` (Memoria de supermercados)
- `id` (UUID, Primary Key)
- `texto_ticket` (Text, Unique) — Nombre tal cual aparece en Mercadona, Lidl, Consum o Dia.
- `nombre_limpio` (Text)
- `es_alimentacion` (Boolean) — `True` si es comida, `False` si es producto de hogar/limpieza/higiene para ignorarlo en la despensa nutricional.
- `supermercado` (Text)
- `gramos_habituales` (Numeric)
- `es_indivisible` (Boolean)
- `ubicacion_defecto` (Text) — `nevera`, `congelador`, `despensa`, `hogar_no_inventariar`.

### Tabla 3: `recetas`
- `id` (UUID, Primary Key)
- `titulo` (Text)
- `tipo` (Text) — `batch_plato_cerrado`, `batch_componente`, `receta_suelta`, `desayuno`, `snack_merienda`.
- `aprobada` (Boolean) — `True` si está en el catálogo fijo de favoritas.
- `comidas_pareja_por_olla` (Integer) — Para cuántos días/comidas de los dos da esta elaboración.
- `guia_emplatado` (Text) — Cómo repartir la olla en tápers y cuántos cazos se sirve Gonzalo (55%) y Marta (45%).
- `ingredientes_json` (JSONB)
- `pasos_preparacion` (Text)
- `nutricion_por_comida_pareja` (JSONB)
- `ultima_vez_cocinada` (Date, opcional) — Se actualiza automáticamente cada vez que se cocina esa receta para poder preguntarle a la IA "¿Qué día hicimos este plato por última vez?".

### Tabla 4: `registro_comidas` (Historial de Cocinado y Consumo Nutricional)
- `id` (UUID, Primary Key)
- `fecha_consumo` (Date) — Día en que se come.
- `fecha_cocinado` (Date) — Día en que se cocinó ese plato.
- `momento` (Text) — `desayuno`, `comida`, `merienda`, `cena`, `snack`.
- `receta_id` (UUID, opcional)
- `tipo_reparto` (Text) — `estandar_55_45`, `mitad_50_50`, `solo_gonzalo`, `solo_marta`.
- `descripcion` (Text)
- `completado` (Boolean)
- `nutricion_gonzalo` (JSONB)
- `nutricion_marta` (JSONB)

### Tabla 5: `lista_compra` (Segundo Cerebro de Compras)
- `id` (UUID, Primary Key)
- `item` (Text) — Ej: "Contramuslos de pollo (1 kg)", "Papel de cocina", "Yogur griego ligero (4 uds)".
- `categoria` (Text) — `frescos`, `despensa`, `congelados`, `hogar_y_otros`.
- `origen` (Text) — `plan_recetas`, `manual_o_voz`.
- `comprado` (Boolean) — `False` por defecto; pasa a `True` al marcarlo en el súper o al subir el ticket.
- `fecha_anadido` (Date)

---

## 4. Flujos de las 4 Pantallas Moviles

### Pantalla 1: Planificacion con IA y Lista de la Compra (Segundo Cerebro)
- **Planificador asistido por IA:** El usuario elige recetas aprobadas o le pide a la IA que diseñe el Batch Cooking y la semana cumpliendo las reglas clínicas.
- **Lista de la Compra Unificada:** Muestra todo lo que hay que comprar en el súper dividido por pasillos (Frescos, Despensa, Hogar/Otros). Permite añadir cualquier cosa suelta a mano o con voz en cualquier momento de la semana.
- **Subida de Ticket (PDF, Foto o CSV):** Tacha lo comprado de la lista, descarta productos de limpieza/hogar y mete la comida en Nevera, Congelador o Despensa.

### Pantalla 2: Cocina Diaria, Control de Tápers, Foto en Encimera y Rescate
- **Cocinar Batch o Receta:** Registra que hoy se ha cocinado un plato (`fecha_cocinado = hoy`), actualiza `ultima_vez_cocinada` en la receta y mete las raciones resultantes en `batch_cocinado` indicando visualmente cuántos días lleva hecho cada táper.
- **Comer Ración:** Resta 1 comida de pareja del táper o de la despensa y suma las calorías y micronutrientes del día a Gonzalo y Marta.
- **Foto en Encimera:** Haces foto a los ingredientes crudos sobre la encimera -> la IA los reconoce, pregunta si es para comer hoy o para guardar raciones de Batch, resta del inventario y registra la fecha de cocinado y los nutrientes.
- **Modo Miércoles/Jueves (Recetas de Rescate):** La IA mira qué tápers llevan más días en la nevera, qué queda en el congelador y qué vitaminas/minerales faltan esa semana para proponer cómo cerrar la semana.

### Pantalla 3: Asistente por Voz y Consultor con Memoria
- Micrófono directo (`st.audio_input`) y chat rápido donde la IA tiene todo el contexto clínico y de base de datos.
- Casos de uso directos por voz:
  1. *"¿Qué día cocinamos las lentejas que están en la nevera?"* o *"¿Cuándo fue la última vez que hicimos salmón?"*.
  2. *"Apúntame en la lista de la compra bolsas de basura, café y aguacates"*.
  3. *"Danos una idea rápida de cena antirreflujo para hoy con lo que queda en la nevera"*.
  4. *"Hemos desayunado yogur griego con avena y nueces, regístralo"*.

### Pantalla 4: Control Nutricional, Vitaminico y Salud
- Tarjetas diarias individuales (Gonzalo 1.700 kcal vs. Marta 1.350 kcal) con barra de proteínas, carbos complejos, fibra y grasas desglosadas.
- Panel semanal completo de Vitaminas, Minerales y Semáforos Clínicos (Hierro + biodisponibilidad, Vitamina D, LDL, Ácido Úrico y Reflujo).