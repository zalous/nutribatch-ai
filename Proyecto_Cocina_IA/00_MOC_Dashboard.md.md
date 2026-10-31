---
proyecto: NutriBatch AI (Planificador de Cocina e Inventario)
estado: fase-4-paso-4.1-validado
fecha_actualizacion: 2026-10-31
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
- **Fase Actual:** **Fase 4 en curso**: **Paso 4.1 validado por el usuario el 31/10/2026**. Fase 3 cerrada.
- **Último avance (31/10/2026):** **Paso 4.1 terminado y validado**. Implementado en `e98bc00`, corregido tras la primera prueba en `6bac0a8` y con una mejora final del emparejamiento con inventario en `7811d3b`. En **🍳 Cocina → 🍳 Acciones** hay tres pestañas:
  1. **🍳 Registrar Cocinado:** elige receta, fecha real, número de tápers y destino (Tápers Batch, Nevera o Congelador). Inserta un táper por comida de pareja con `fecha_cocinado`, `fecha_entrada`, `cantidad_aprox = "1 comida de pareja"` y la nutrición por comida de pareja de la receta, y actualiza `ultima_vez_cocinada` en `recetas`. Si la receta no tiene nutrición, se puede añadir para esos tápers (sin modificar la receta) o guardar con aviso.
  2. **✅ Check Comido:** elige cualquier ítem de nevera/congelador/despensa/tápers, momento, fecha de consumo y reparto (55/45, 50/50, solo Gonzalo o solo Marta). Permite indicar la cantidad real consumida (ración completa o parcial: 0,25/0,5… o gramos), descuenta proporcionalmente y borra el ítem solo al agotarse; los indivisibles se consumen enteros. Los nutrientes se escalan a lo consumido. Guarda en `registro_comidas` la descripción con la cantidad, `fecha_cocinado`, `receta_id` si se reconoce y `nutricion_gonzalo` / `nutricion_marta` repartidas. Los nutrientes salen del táper, de una receta guardada o se introducen a mano; también se puede registrar sin nutrientes.
  3. **📸 Foto en Encimera:** el usuario elige *subir del carrete* (por defecto, cámara apagada) o *hacer foto con la cámara*. Gemini Vision reconoce ingredientes crudos con el perfil clínico, el inventario como referencia y un campo de contexto libre ("el pavo lo he marinado yo"). Devuelve el producto del inventario con el que se corresponde cada ingrediente; la tabla permite cambiarlo a mano o marcar *No descontar*. El usuario elige **comida de hoy** (registra consumo y nutrientes con reparto) o **batch** (crea tápers con fecha y nutrición) y confirma. La estimación nutricional es editable y nunca se inventan gramos.
- **Validación:** el usuario probó el 31/10/2026 las tres acciones con las correcciones (cámara opcional, contexto/cruce de inventario y consumo parcial) y dio el Paso 4.1 por finalizado.
- **Pasos anteriores validados:** 3.1 en `952706e` (motor IA contextual), 3.2 en `aa3d4b8` (recetas y reparto 55/45) y 3.3 en `c1ab194` + `7d589ca` (lista de la compra "Segundo Cerebro" con suma de cantidades).
- **Cambio técnico relevante:** `ai_engine.py` incorpora `reconocer_ingredientes_encimera()` con el modelo estructurado `ResultadoEncimera` (ingredientes, `nombre_inventario`, `notas`, descripción, comidas de pareja y nutrición estimada), perfil clínico, contexto libre del usuario e inventario como referencia; reutiliza el fallback de modelos y la gestión de cuota. `database.py` incorpora `add_items_inventario()` (inserción masiva de tápers), `add_registro_comida()` y la coincidencia difusa `puntuar_coincidencia()` / `mejor_coincidencia_producto()`, que ignora palabras de preparación (adobado, marinado, fileteado…), unifica plurales/género y prioriza el alimento base del inventario. El Check Comido descuenta cantidades parciales y escala los nutrientes; los indivisibles se consumen enteros. La foto usa claves de widgets dinámicas por análisis. **No hay migración de base de datos:** `supabase_init.sql` no se ha tocado.
- **Archivos de código creados/modificados en esta sesión:** `ai_engine.py`, `database.py`, `views/p2_cocinar_hoy.py`, `Proyecto_Cocina_IA/01_Spec_Tecnico_y_Funcional.md` (v1.9), `Proyecto_Cocina_IA/00_MOC_Dashboard.md.md`, `Proyecto_Cocina_IA/sesiones/2026-10-31_sesion.md`.
- **Próximo paso exacto:** **Paso 4.2 — Recetas de Rescate (Miércoles/Jueves)**. Implementar una acción que analice las sobras de nevera/congelador, la antigüedad de los tápers cocinados y los huecos de macros/vitaminas/minerales de la semana para proponer recetas de rescate. **No empezar el Paso 4.2 sin la confirmación explícita del usuario.**

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
- [x] **Paso 3.3:** Lista de la Compra "Segundo Cerebro" (une automáticamente los ingredientes que faltan para las recetas de la semana + cosas sueltas de casa o básicos añadidos a mano o por voz durante la semana). *(Implementado y desplegado en `c1ab194`; cantidades y sincronización corregidas en `7d589ca`; validado por el usuario el 25/10/2026)*

### Fase 4: Dia a Dia (Checks de Racion, Foto en Encimera, Voz con Memoria y Rescate)
REPASAR FUNCIONAMIENTO DÍA A DÍA Y NUTRIENTES
- [x] **Paso 4.1:** Botón de "Registrar Cocinado" (guarda la `fecha_cocinado` exacta del lote o receta) y "Check Comido" (descuenta 1 comida de pareja y suma nutrientes del día). Incluye función "Foto en Encimera" para descontar ingredientes sueltos con la cámara. *(Implementado en `e98bc00`, corregido en `6bac0a8` y validado por el usuario el 31/10/2026)*
- [ ] **Paso 4.2:** Botón de "Recetas de Rescate (Miércoles/Jueves)" según sobras de nevera/congelador, antigüedad de los tápers cocinados y huecos de macros/vitaminas/minerales de la semana.
- [ ] **Paso 4.3:** Asistente por Voz y Chat Contextual: permite pedir recetas adaptadas al momento, añadir cosas a la lista de la compra hablando o preguntar "¿Qué día cocinamos tal plato?" consultando el historial y la nevera. También se le puede decir que un alimento o táper ya se consumió y que lo actualice el almacenaje donde toque (nevera, despensa, congelador o tápers). Por último, que marque una receta o táper como "Check Comido" si se le pide (descuenta 1 comida de pareja y suma nutrientes del día). 

### Fase 5: Cuadro de Mando Nutricional, Vitaminico y Clinico Completo
- [ ] **Paso 5.1 (Panel Diario de Macros por Persona):** Tarjetas detalladas para Gonzalo (1.700 kcal) y Marta (1.350-1.400 kcal) con Calorías, Proteínas, Carbohidratos complejos, Fibra (soluble/insoluble), Azúcares libres y Grasas desglosadas (Mono, Poli/Omega-3 y tope de Saturadas).
- [ ] **Paso 5.2 (Panel Semanal de Micronutrientes y Alertas Clínicas):** Barras de progreso semanal (% CDR) de Vitaminas (D, C, B12, B9, B6, B1, B2, B3, A, E, K), Minerales (Hierro + biodisponibilidad, Magnesio, Potasio, Calcio, Zinc, Selenio, Fósforo, Sodio) y Semáforos Clínicos (Purinas/Ácido Úrico, LDL y Antirreflujo).