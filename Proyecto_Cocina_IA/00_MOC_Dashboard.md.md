---
proyecto: NutriBatch AI (Planificador de Cocina e Inventario)
estado: fase-2-pendiente-validacion
fecha_actualizacion: 2026-10-22
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
- **Fase Actual:** Fase 2 - Despensa Aproximada, Control de Fechas de Cocinado y Tickets.
- **Último avance:** Pasos 2.2 y 2.3 completados. El lector de tickets ya funciona con texto, CSV, PDF digital y visión (fotos) mediante Gemini. `GEMINI_API_KEY` configurada en `.streamlit/secrets.toml` (local, validada con una imagen de prueba: 6 productos, hogar filtrado, sin cabeceras ni totales) y añadida por el usuario a los Secrets de Streamlit Community Cloud.
- **Cambio técnico relevante:** `gemini-2.5-flash` fue retirado para claves nuevas (octubre 2026). El motor usa ahora `gemini-3.6-flash` como principal, con respaldo automático a `gemini-3.5-flash`, `gemini-3.7-flash` y `gemini-3.8-flash`, y reintentos ante errores 429/503. Documentado en `01_Spec_Tecnico_y_Funcional.md` v1.1 y en `AGENTS.md`.
- **Archivos de código creados/modificados:** `ai_engine.py`, `views/p1_plan_y_compra.py`, `AGENTS.md`, `Proyecto_Cocina_IA/01_Spec_Tecnico_y_Funcional.md`, `Proyecto_Cocina_IA/00_MOC_Dashboard.md.md`, `Proyecto_Cocina_IA/sesiones/2026-10-22_sesion.md`.
- **Validación pendiente (la hace el usuario al inicio de la próxima sesión):** subir una **foto real de ticket** desde el móvil en `🛒 Compra > 🧾 Subir Ticket` con la app ya reiniciada en Streamlit Cloud, y confirmar que detecta bien los productos.
- **Próximo paso exacto:** Confirmar el test real de la foto de ticket. Si funciona, ejecutar el **Paso 2.4** (interfaz de revisión editable: borrar/editar filas antes de guardar, cruce con `lista_compra`, alta en `diccionario_tickets` e `inventario`). Si falla, depurar el error concreto antes de continuar.

---

## Roadmap de Construccion (Paso a Paso)

### Fase 1: Cimientos Cloud (Coste 0 euros)
- [x] **Paso 1.1:** Crear archivo `AGENTS.md` y script `supabase_init.sql` con las 5 tablas (`inventario`, `diccionario_tickets`, `recetas`, `registro_comidas`, `lista_compra`).
- [x] **Paso 1.2:** Crear archivos `requirements.txt`, `database.py` y `app.py` básico, subir a GitHub y conectar con Streamlit Community Cloud para verlo desde los dos móviles.

### Fase 2: Despensa Aproximada, Control de Fechas de Cocinado y Tickets
- [x] **Paso 2.1:** Pantalla de Inventario (Nevera, Congelador, Despensa Seca y Tápers Cocinados mostrando claramente qué día se cocinó cada plato y cuántos días lleva hecho).
- [x] **Paso 2.2:** Analizador sintáctico robusto de texto/CSV para tickets (limpieza inteligente de cabeceras corporativas, CIFs, direcciones, IVA y totales de pago, extracción limpia de alimentos y filtrado de productos de hogar/limpieza).
- [x] **Paso 2.3:** Configuración de Google Gemini API Key (`GEMINI_API_KEY`) en secrets (local y Streamlit Cloud) e integración del modelo `gemini-3.6-flash` para visión artificial multimodal de fotos y PDFs de tickets. *(Validado en local; el usuario ya añadió la clave a Streamlit Cloud y hará el test real de foto la próxima sesión)*
- [ ] **Paso 2.4:** Validación y prueba interactiva del flujo de tickets: interfaz de edición y descarte de filas antes de guardar, cruce con `lista_compra`, guardado en `diccionario_tickets` y carga a `inventario`.

### Fase 3: Motor IA Contextual, Recetas, Batch Cooking y Lista de la Compra (Segundo Cerebro)
- [ ] **Paso 3.1:** Crear `ai_engine.py` inyectando de forma permanente `02_Perfil_Clinico_y_Nutricional.md` + el estado actual del inventario, tápers con sus fechas de cocinado e historial.
- [ ] **Paso 3.2:** Gestor de Recetas Aprobadas y Batch Cooking (indicando cuántas comidas de pareja salen de la olla y el reparto en plato 55% Gonzalo / 45% Marta para cuadrar las 1.700 kcal y 1.350 kcal).
- [ ] **Paso 3.3:** Lista de la Compra "Segundo Cerebro" (une automáticamente los ingredientes que faltan para las recetas de la semana + cosas sueltas de casa o básicos añadidos a mano o por voz durante la semana).

### Fase 4: Dia a Dia (Checks de Racion, Foto en Encimera, Voz con Memoria y Rescate)
- [ ] **Paso 4.1:** Botón de "Registrar Cocinado" (guarda la `fecha_cocinado` exacta del lote o receta) y "Check Comido" (descuenta 1 comida de pareja y suma nutrientes del día). Incluye función "Foto en Encimera" para descontar ingredientes sueltos con la cámara.
- [ ] **Paso 4.2:** Botón de "Recetas de Rescate (Miércoles/Jueves)" según sobras de nevera/congelador, antigüedad de los tápers cocinados y huecos de macros/vitaminas/minerales de la semana.
- [ ] **Paso 4.3:** Asistente por Voz y Chat Contextual: permite pedir recetas adaptadas al momento, añadir cosas a la lista de la compra hablando o preguntar "¿Qué día cocinamos tal plato?" consultando el historial y la nevera.

### Fase 5: Cuadro de Mando Nutricional, Vitaminico y Clinico Completo
- [ ] **Paso 5.1 (Panel Diario de Macros por Persona):** Tarjetas detalladas para Gonzalo (1.700 kcal) y Marta (1.350-1.400 kcal) con Calorías, Proteínas, Carbohidratos complejos, Fibra (soluble/insoluble), Azúcares libres y Grasas desglosadas (Mono, Poli/Omega-3 y tope de Saturadas).
- [ ] **Paso 5.2 (Panel Semanal de Micronutrientes y Alertas Clínicas):** Barras de progreso semanal (% CDR) de Vitaminas (D, C, B12, B9, B6, B1, B2, B3, A, E, K), Minerales (Hierro + biodisponibilidad, Magnesio, Potasio, Calcio, Zinc, Selenio, Fósforo, Sodio) y Semáforos Clínicos (Purinas/Ácido Úrico, LDL y Antirreflujo).