---
proyecto: NutriBatch AI (Planificador de Cocina e Inventario)
estado: fase-3-en-curso-pendiente-validar-paso-3.3
fecha_actualizacion: 2026-10-25
---
# Panel de Control y Contexto IA

## Archivos del Sistema
- [[01_Spec_Tecnico_y_Funcional]]
- [[02_Perfil_Clinico_y_Nutricional]]

---

## PROTOCOLO PARA RETOMAR SESION CON LA IA (OPENCODE)
1. Al iniciar sesión en OpenCode: Pide al agente leer `AGENTS.md` y las notas dentro de `Proyecto_Cocina_IA/`.
2. Durante la sesión: Pide desarrollar un único paso del Roadmap cada vez. Todo el código lo crea y edita el agente directamente.
3. Antes de cerrar: Dile a OpenCode "Cerramos sesión" para que actualice el bloque "ESTADO ACTUAL", marque las casillas completadas y guarde el resumen en `sesiones/`.

---

## ESTADO ACTUAL
- **Fase Actual:** Fase 3 en curso: **Pasos 3.1 y 3.2 validados por el usuario**; **Paso 3.3 implementado, pendiente de validación**.
- **Último avance:** **Paso 3.1 validado** ("Está ok", commit `952706e`): `ai_engine.py` inyecta `02_Perfil_Clinico_y_Nutricional.md` como `system_instruction` permanente junto al inventario, los tápers con `fecha_cocinado`/días transcurridos, el historial de `registro_comidas` y la lista de la compra pendiente. La pestaña Voz permite una **consulta de texto de solo lectura** con el contexto vivo y un desplegable para revisarlo.
- **Paso 3.2 validado por el usuario el 25/10/2026:** commit `aa3d4b8`. `views/recetas_batch.py` integrado en **Compra → 🍲 Recetas y Batch**: catálogo con búsqueda/filtro de aprobadas, alta/edición/borrado de recetas, ingredientes y nutrición opcional **por comida de pareja**, y cálculo automático del reparto **55% Gonzalo / 45% Marta**, total de la olla y % sobre 1.700/1.350 kcal.
- **Paso 3.3 implementado y subido a `main`; pendiente de validación:** nuevo `views/lista_compra_inteligente.py` en **Compra → 📝 Lista de la Compra**. Permite elegir las recetas de la semana y cruza sus ingredientes con nevera/congelador/despensa, los ítems ya comprados y la lista pendiente. Clasifica cada ingrediente como **✅ En despensa / 🛍️ Ya comprado / 📝 Ya en la lista / ➕ Falta** y añade todos los faltantes con un botón (`origen = plan_recetas`). Los ingredientes repetidos entre recetas se agrupan y sus cantidades se muestran sumadas. La selección se conserva en la URL (`?plan=id1,id2`).
- **Cambio técnico relevante:** el perfil clínico se lee de forma nativa desde el `.md` y se cachea; el contexto vivo se limita (80 ítems por ubicación, 25 comidas de historial y 100 ítems de compra) y los fallos de lectura se informan sin romper la consulta. Las recetas guardan `ingredientes_json` como `[{"nombre", "cantidad"}]` y `nutricion_por_comida_pareja` con claves como `kcal`, `proteinas_g`, `fibra_g`, etc.; solo se guardan valores > 0 y **nunca se inventan nutrientes**. La lista inteligente excluye los `batch_cocinado` del cruce de ingredientes crudos, normaliza plurales y evita duplicados. `database.py` incorpora `add_items_lista_compra()` (inserción masiva) y el cruce público `coincide_producto()`. **No hay migración de base de datos.**
- **Archivos de código creados/modificados:** `ai_engine.py`, `database.py`, `views/p3_asistente_voz.py`, `views/recetas_batch.py`, `views/lista_compra_inteligente.py` (nuevo), `views/p1_plan_y_compra.py`, `Proyecto_Cocina_IA/01_Spec_Tecnico_y_Funcional.md` (v1.7), `Proyecto_Cocina_IA/00_MOC_Dashboard.md.md`, `Proyecto_Cocina_IA/sesiones/2026-10-25_sesion_2.md`.
- **Próximo paso exacto:** **validar el Paso 3.3** en la app: crear/abrir al menos dos recetas aprobadas con ingredientes repetidos, seleccionarlas en **Lista de la Compra → Segundo Cerebro**, comprobar el cruce con la despensa y la lista, y pulsar **➕ Añadir faltantes**. Verificar que no se duplican ítems si se vuelve a pulsar y que la selección se mantiene al recargar. Si el usuario da el OK, marcar `[x]` el Paso 3.3 y ejecutar el **Paso 4.1**: botones "Registrar Cocinado" y "Check Comido" + "Foto en Encimera".

---

## Roadmap de Construccion (Paso a Paso)

### Fase 1: Cimientos Cloud (Coste 0 euros)
- [x] **Paso 1.1:** Crear archivo `AGENTS.md` y script `supabase_init.sql` con las 5 tablas (`inventario`, `diccionario_tickets`, `recetas`, `registro_comidas`, `lista_compra`).
- [x] **Paso 1.2:** Crear archivos `requirements.txt`, `database.py` y `app.py` básico, subir a GitHub y conectar con Streamlit Community Cloud para verlo desde los dos móviles.

### Fase 2: Despensa Aproximada, Control de Fechas de Cocinado y Tickets
- [x] **Paso 2.1:** Pantalla de Inventario (Nevera, Congelador, Despensa Seca y Tápers Cocinados mostrando claramente qué día se cocinó cada plato y cuántos días lleva hecho).
- [x] **Paso 2.2:** Analizador sintáctico robusto de texto/CSV para tickets (limpieza inteligente de cabeceras corporativas, CIFs, direcciones, IVA y totales de pago, extracción limpia de alimentos y filtrado de productos de hogar/limpieza).
- [x] **Paso 2.3:** Configuración de Google Gemini API Key (`GEMINI_API_KEY`) en secrets (local y Streamlit Cloud) e integración del modelo `gemini-3.6-flash` para visión artificial multimodal de fotos y PDFs de tickets. *(Validado en local y en Streamlit Cloud con foto real de ticket el 22/10/2026, usando una clave nueva en proyecto nuevo)*
- [x] **Paso 2.4:** Validación y prueba interactiva del flujo de tickets: interfaz de edición y descarte de filas antes de guardar, cruce con `lista_compra`, guardado en `diccionario_tickets` y carga a `inventario`. *(Implementado y validado por el usuario el 24/10/2026)*
- [x] **Paso 2.5:** Gestión masiva de la Despensa: selección múltiple de productos para borrarlos de una sola vez, opción de vaciar la pestaña actual (Nevera, Congelador, Despensa Seca o Tápers Batch) y opción de borrar todo el inventario con confirmación por texto (`BORRAR`). Incluye borrado masivo equivalente en la Lista de la Compra. *(Implementado y validado por el usuario el 24/10/2026)*
- [x] **Paso 2.6:** Revisión y ajustes de usabilidad: **(a)** no inventar gramos en la tabla del ticket ni al guardar: si la IA no conoce el peso, dejar el campo vacío; **(b)** simplificar la Lista de la Compra: quitar el aspa ❌ de borrado y los emojis/categorías de cada ítem, de forma que pulsar el propio ítem lo marque o lo quite de la lista, mostrándose solo como una lista limpia de ítems; **(c)** el formulario de alta solo pide el nombre del producto, sin selector de categoría (frescos/despensa/congelados/hogar). *(Implementado, desplegado en `a4df9d3` y validado por el usuario el 25/10/2026)*

### Fase 3: Motor IA Contextual, Recetas, Batch Cooking y Lista de la Compra (Segundo Cerebro)
- [x] **Paso 3.1:** Crear `ai_engine.py` inyectando de forma permanente `02_Perfil_Clinico_y_Nutricional.md` + el estado actual del inventario, tápers con sus fechas de cocinado e historial. *(Implementado, desplegado en `952706e` y validado por el usuario el 25/10/2026)*
- [x] **Paso 3.2:** Gestor de Recetas Aprobadas y Batch Cooking (indicando cuántas comidas de pareja salen de la olla y el reparto en plato 55% Gonzalo / 45% Marta para cuadrar las 1.700 kcal y 1.350 kcal). *(Implementado y desplegado en `aa3d4b8`; validado por el usuario el 25/10/2026)*
- [ ] **Paso 3.3:** Lista de la Compra "Segundo Cerebro" (une automáticamente los ingredientes que faltan para las recetas de la semana + cosas sueltas de casa o básicos añadidos a mano o por voz durante la semana). *(Implementado el 25/10/2026; pendiente de validación por el usuario)*

### Fase 4: Dia a Dia (Checks de Racion, Foto en Encimera, Voz con Memoria y Rescate)
- [ ] **Paso 4.1:** Botón de "Registrar Cocinado" (guarda la `fecha_cocinado` exacta del lote o receta) y "Check Comido" (descuenta 1 comida de pareja y suma nutrientes del día). Incluye función "Foto en Encimera" para descontar ingredientes sueltos con la cámara.
- [ ] **Paso 4.2:** Botón de "Recetas de Rescate (Miércoles/Jueves)" según sobras de nevera/congelador, antigüedad de los tápers cocinados y huecos de macros/vitaminas/minerales de la semana.
- [ ] **Paso 4.3:** Asistente por Voz y Chat Contextual: permite pedir recetas adaptadas al momento, añadir cosas a la lista de la compra hablando o preguntar "¿Qué día cocinamos tal plato?" consultando el historial y la nevera. También se le puede decir que un alimento o táper ya se consumió y que lo actualice el almacenaje donde toque (nevera, despensa, congelador o tápers). Por último, que marque una receta o táper como "Check Comido" si se le pide (descuenta 1 comida de pareja y suma nutrientes del día). 

### Fase 5: Cuadro de Mando Nutricional, Vitaminico y Clinico Completo
- [ ] **Paso 5.1 (Panel Diario de Macros por Persona):** Tarjetas detalladas para Gonzalo (1.700 kcal) y Marta (1.350-1.400 kcal) con Calorías, Proteínas, Carbohidratos complejos, Fibra (soluble/insoluble), Azúcares libres y Grasas desglosadas (Mono, Poli/Omega-3 y tope de Saturadas).
- [ ] **Paso 5.2 (Panel Semanal de Micronutrientes y Alertas Clínicas):** Barras de progreso semanal (% CDR) de Vitaminas (D, C, B12, B9, B6, B1, B2, B3, A, E, K), Minerales (Hierro + biodisponibilidad, Magnesio, Potasio, Calcio, Zinc, Selenio, Fósforo, Sodio) y Semáforos Clínicos (Purinas/Ácido Úrico, LDL y Antirreflujo).