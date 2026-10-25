---
documento: Spec Técnico y Funcional
version: 1.7
stack: Python + Streamlit Cloud + Supabase + Gemini 3.6 Flash
---
# Especificacion Tecnica y Funcional

## 1. Reglas de Oro para la IA Desarrolladora y para la IA de la App
1. **Cero código manual por parte del usuario:** El agente de código crea y edita todos los archivos completos. Prohibido truncar código.
2. **Arquitectura 100% Online, Gratis y Sin Servidor Propio:**
   - **Frontend y Backend:** Python (`streamlit`) alojado gratis en Streamlit Community Cloud.
   - **Base de Datos:** `supabase` (PostgreSQL en la nube, capa gratuita).
   - **Motor IA (Texto, Visión y Audio):** `google-genai` usando `gemini-3.6-flash` como modelo principal, con respaldo automático a `gemini-3.5-flash`, `gemini-3.7-flash`, `gemini-3.8-flash` y, como última red, a los ligeros `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite`. Respuestas estructuradas (`pydantic`). Nota: `gemini-2.5-flash` ya no está disponible para claves nuevas desde octubre de 2026.
   - **Gestión de cuota y errores:** la cuota gratuita es de **20 peticiones/día por modelo y por proyecto**. Ante un 429 (`RESOURCE_EXHAUSTED`) no se reintenta: el modelo se marca como agotado en `st.session_state` y se salta al siguiente durante esa sesión. Solo se reintenta una vez ante 503/`UNAVAILABLE` (saturación puntual). Una clave nueva solo estrena cuota si pertenece a un **proyecto nuevo** de Google AI Studio.
   - **Credenciales:** la `GEMINI_API_KEY` se guarda en `.streamlit/secrets.toml` (local) y en los Secrets de Streamlit Community Cloud (producción), nunca en GitHub.
3. **Cerebro IA Especializado (Inyección de Contexto Permanente):**
   - El módulo `ai_engine.py` debe cargar siempre como `system_instruction` las reglas médicas, de porciones y de alimentos de `02_Perfil_Clinico_y_Nutricional.md`.
   - Además, en cada consulta del usuario (por voz o botón), se le inyectará el contexto vivo de Supabase: qué hay en `inventario` (con sus fechas de cocinado), qué hay pendiente en `lista_compra` y cuándo se cocinaron los últimos platos en `registro_comidas`.
4. **Filosofía de Inventario, Lotes (Batch) y Fechas de Cocinado:**
   - **Sin básculas:** Cantidades lógicas o aproximadas (unidades, bandejas, tápers). Los gramos son opcionales: si la IA no conoce el peso se dejan vacíos y nunca se inventan; en los tickets solo se guardan cuando el peso aparece escrito de forma explícita (`kg`, `g`, `L`).
   - **Control de Fecha de Cocinado (`fecha_cocinado`):** Cada vez que se cocina un lote de Batch Cooking o una receta que se guarda, se registra exactamente qué día se cocinó. Así la app muestra cuántos días lleva hecho cada táper en la nevera/congelador y la IA puede responder preguntas como "¿Qué día cocinamos las lentejas o el pollo?".
   - **Lógica de Ollas y Raciones:** Las recetas grandes definen cuántas **comidas de pareja** salen de la olla entera (ej. 1 olla = 3 comidas para los dos). Al comer entre semana, se resta solo 1 comida de pareja del lote y se suman únicamente los nutrientes de esa toma individual (aprox. 55% Gonzalo / 45% Marta en guisos para cuadrar 1.700 kcal y 1.350 kcal, o 50/50 en unidades iguales).
   - **Regla de Indivisibles (Regla de la Dorada):** Alimentos que se gastan enteros en una comida nunca se fraccionan crudos.
   - **Segundo Cerebro en Lista de la Compra:** Permite apuntar tanto ingredientes de recetas como productos generales del súper o del hogar (papel, detergente, café, básicos) por texto o por voz. Al subir el ticket del súper, la IA tacha lo comprado de la lista pero solo mete en el `inventario` nutricional lo que sea comida.
   - **Gestión masiva y borrados seguros:** La Despensa permite seleccionar varios productos y borrarlos de una vez, vaciar una ubicación concreta (Nevera, Congelador, Despensa o Tápers) o borrar todo el inventario. El borrado total exige escribir `BORRAR`; vaciar una pestaña exige confirmación por checkbox. La Lista de la Compra ofrece el mismo borrado múltiple y un vaciado total también protegido con `BORRAR`.

---

## 2. Estructura de Archivos del Codigo
En la carpeta raíz del proyecto (fuera de la subcarpeta de Obsidian):
- `.streamlit/config.toml` (Diseño adaptado a pantallas de móvil)
- `.streamlit/secrets.toml` (Credenciales seguras: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`)
- `requirements.txt` (Librerías: `streamlit>=1.49`, `pandas`, `supabase`, `google-genai`, `pydantic`, `pypdf`, `pillow`)
- `app.py` (Menú principal móvil y navegación entre las 4 pantallas)
- `database.py` (Conexión y consultas a Supabase)
- `ai_engine.py` (Cerebro IA con System Prompt clínico/batch, lector de tickets, fotos, voz y planificador)
- **Subcarpeta `views/`:**
  - `p1_plan_y_compra.py` (Planificador con IA, Lista de la Compra Unificada Comida+Hogar y Subida de Ticket. Integra el gestor de recetas y el segundo cerebro de compras)
  - `lista_compra_inteligente.py` (Segundo cerebro de la compra: selector de recetas de la semana, cruce de ingredientes con inventario y lista, suma de cantidades y sincronización automática de faltantes)
  - `recetas_batch.py` (Catálogo de recetas aprobadas, alta/edición/borrado y cálculo del reparto batch 55% Gonzalo / 45% Marta)
  - `p2_cocinar_hoy.py` (Nevera/Congelador con fechas de cocinado, Check de cocinado/comido, Foto en encimera y Recetas de rescate Mié/Jue)
  - `p3_asistente_voz.py` (Consultor por Voz y Texto: pedir ideas de batch/cenas/desayunos, añadir a la lista de la compra o preguntar qué día se cocinó un plato. En la Fase 3 ya ofrece una consulta de texto de solo lectura)
  - `p4_salud_nutri.py` (Progreso diario Gonzalo vs Marta y Panel semanal de macros, vitaminas y minerales)

---

## 3. Esquema de Base de Datos (Supabase)

### Tabla 1: `inventario`
- `id` (UUID, Primary Key)
- `nombre` (Text) — Ej: "Pechuga de pollo", "Dorada", "Táper Lentejas con verduras".
- `ubicacion` (Text) — Valores: `nevera`, `congelador`, `despensa`, `batch_cocinado`.
- `cantidad_aprox` (Text) — Ej: "3 unidades", "1 bandeja", "2 comidas de pareja".
- `gramos_estimados` (Numeric, opcional) — Peso estimado por la IA solo si lo conoce de verdad; si no, se deja vacío y nunca se inventa.
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
- `gramos_habituales` (Numeric, opcional) — Peso aprendido de tickets anteriores; vacío si no se conoce, nunca inventado.
- `es_indivisible` (Boolean)
- `ubicacion_defecto` (Text) — `nevera`, `congelador`, `despensa`, `hogar_no_inventariar`.

### Tabla 3: `recetas`
- `id` (UUID, Primary Key)
- `titulo` (Text)
- `tipo` (Text) — `batch_plato_cerrado`, `batch_componente`, `receta_suelta`, `desayuno`, `snack_merienda`.
- `aprobada` (Boolean) — `True` si está en el catálogo fijo de favoritas.
- `comidas_pareja_por_olla` (Integer) — Para cuántos días/comidas de los dos da esta elaboración.
- `guia_emplatado` (Text) — Cómo repartir la olla en tápers y cuántos cazos se sirve Gonzalo (55%) y Marta (45%).
- `ingredientes_json` (JSONB) — Lista de objetos con la forma `[{"nombre": "Lentejas", "cantidad": "300 g"}, ...]`. La cantidad es opcional.
- `pasos_preparacion` (Text)
- `nutricion_por_comida_pareja` (JSONB) — Nutrientes de **una comida de pareja**, nunca de una persona ni de la olla entera. Claves admitidas: `kcal`, `proteinas_g`, `carbohidratos_g`, `grasas_g`, `grasas_saturadas_g`, `fibra_g`, `azucares_g`, `hierro_mg`, `vitamina_c_mg`, `calcio_mg`, `vitamina_d_ug`. Solo se guardan valores mayores que 0 y nunca se inventan. El reparto 55/45 y los totales de la olla se calculan al vuelo y no se almacenan.
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
- **Gestor de Recetas Aprobadas y Batch Cooking (Paso 3.2):** Pestaña **🍲 Recetas y Batch** con métricas de catálogo, buscador, filtro de aprobadas y fichas desplegables. Permite crear, editar, aprobar/desaprobar y eliminar recetas. Cada receta define su tipo, ingredientes, preparación, `comidas_pareja_por_olla` y, opcionalmente, la nutrición por comida de pareja. La app muestra el reparto **55% Gonzalo / 45% Marta**, el total de la olla y el porcentaje que representa sobre las 1.700 kcal de Gonzalo y las 1.350 kcal de Marta. La guía de emplatado se autogenera si se deja vacía.
- **Lista de la Compra Unificada (simplificada en el Paso 2.6):** Se muestra como una lista limpia de ítems, sin emojis, etiquetas de categoría ni aspa de borrado: tocar un ítem pendiente lo marca como comprado y tocar uno ya comprado lo quita de la lista. El formulario de alta solo pide el nombre del producto (la categoría queda como dato interno y usa el valor por defecto de la base de datos). Permite añadir cualquier cosa suelta a mano o con voz en cualquier momento de la semana.
- **Segundo Cerebro de la compra (Paso 3.3):** En la pestaña Lista de la Compra se eligen las recetas de la semana y la app une automáticamente sus ingredientes. Cada ingrediente se clasifica como **✅ En despensa** (coincide con nevera, congelador o despensa; los tápers ya cocinados no cuentan como ingrediente crudo), **🛍️ Ya comprado**, **📝 Ya en la lista**, **🔄 Actualizar cantidad** o **➕ Falta**. Un solo botón añade todos los faltantes con `origen = plan_recetas` y categoría interna inferida. Los ingredientes repetidos entre recetas se agrupan y **sus cantidades se suman numéricamente por unidad** (500 g + 500 g = 1.000 g; también convierte kg→g, l→ml y fracciones como 1/2 kg), mostrando por separado los grupos incompatibles (por ejemplo, 500 g + 2 unidades). Si una receta cambia y un ítem ya generado por el plan tiene una cantidad antigua, se marca como **🔄 Actualizar cantidad** y la sincronización corrige el texto sin duplicarlo. La selección de recetas se conserva en la URL (`?plan=id1,id2`) para no perderla al recargar. **No requiere cambios de esquema ni migración de base de datos.**
- **Subida de Ticket (PDF, Foto o CSV):** Tacha lo comprado de la lista, descarta productos de limpieza/hogar y mete la comida en Nevera, Congelador o Despensa.
- **Revisión editable del ticket (Paso 2.4):** Antes de guardar nada, la vista previa se muestra como tabla editable (`st.data_editor`): se puede cambiar el nombre limpio, marcar/desmarcar si es comida, cambiar la ubicación de destino, ajustar la cantidad, marcar indivisible, desmarcar la casilla `Incluir` para descartar una fila o borrarla directamente. Botones rápidos para descartar todo lo de hogar o restaurar la vista original. Solo las filas incluidas se guardan en `diccionario_tickets` e `inventario`, y solo esas cruzan con `lista_compra`. **Los gramos solo se rellenan si el ticket los muestra de forma explícita (`kg`, `g`, `L`): el parser local no los estima y Gemini los descarta cuando no constan; si no aparecen, quedan vacíos y nunca se guardan (Paso 2.6).**

### Pantalla 2: Cocina Diaria, Control de Tápers, Foto en Encimera y Rescate
- **Cocinar Batch o Receta:** Registra que hoy se ha cocinado un plato (`fecha_cocinado = hoy`), actualiza `ultima_vez_cocinada` en la receta y mete las raciones resultantes en `batch_cocinado` indicando visualmente cuántos días lleva hecho cada táper.
- **Comer Ración:** Resta 1 comida de pareja del táper o de la despensa y suma las calorías y micronutrientes del día a Gonzalo y Marta.
- **Foto en Encimera:** Haces foto a los ingredientes crudos sobre la encimera -> la IA los reconoce, pregunta si es para comer hoy o para guardar raciones de Batch, resta del inventario y registra la fecha de cocinado y los nutrientes.
- **Modo Miércoles/Jueves (Recetas de Rescate):** La IA mira qué tápers llevan más días en la nevera, qué queda en el congelador y qué vitaminas/minerales faltan esa semana para proponer cómo cerrar la semana.
- **Gestión masiva de la despensa (Paso 2.5):** Cada pestaña permite seleccionar varios productos con checkbox (incluido "seleccionar todos") y borrarlos de una sola vez. Además, un desplegable "Zona peligrosa" ofrece vaciar solo la pestaña actual o borrar todo el inventario; el borrado total exige escribir la palabra `BORRAR` como confirmación. La Lista de la Compra tiene el mismo borrado múltiple.

### Pantalla 3: Asistente por Voz y Consultor con Memoria
- **Consulta contextual de solo lectura (Paso 3.1, ya disponible):** La pestaña Voz permite escribir una pregunta y recibir respuesta de Gemini con el `system_instruction` clínico permanente y el contexto vivo de Supabase (inventario, tápers con `fecha_cocinado` y días transcurridos, historial de comidas y lista de la compra pendiente). Incluye un desplegable para revisar el contexto enviado. Este modo no modifica la base de datos.
- **Fase 4:** Micrófono directo (`st.audio_input`) y chat rápido donde la IA tiene todo el contexto clínico y de base de datos, además de poder ejecutar acciones (añadir a la compra, actualizar inventario o marcar "Check Comido").
- Casos de uso directos por voz:
  1. *"¿Qué día cocinamos las lentejas que están en la nevera?"* o *"¿Cuándo fue la última vez que hicimos salmón?"*.
  2. *"Apúntame en la lista de la compra bolsas de basura, café y aguacates"*.
  3. *"Danos una idea rápida de cena antirreflujo para hoy con lo que queda en la nevera"*.
  4. *"Hemos desayunado yogur griego con avena y nueces, regístralo"*.

### Pantalla 4: Control Nutricional, Vitaminico y Salud
- Tarjetas diarias individuales (Gonzalo 1.700 kcal vs. Marta 1.350 kcal) con barra de proteínas, carbos complejos, fibra y grasas desglosadas.
- Panel semanal completo de Vitaminas, Minerales y Semáforos Clínicos (Hierro + biodisponibilidad, Vitamina D, LDL, Ácido Úrico y Reflujo).