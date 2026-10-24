# AGENTS.md — Reglas Permanentes de Trabajo (OpenCode)

Este documento define el protocolo operativo estricto e inmutable para el agente OpenCode en el proyecto **NutriBatch AI**.

---

## 1. Protocolo de Inicio de Sesión
Al iniciar cualquier sesión de trabajo, el agente DEBE leer obligatoriamente las siguientes notas maestras en la subcarpeta `Proyecto_Cocina_IA/`:
1. `Proyecto_Cocina_IA/00_MOC_Dashboard.md.md` (o `00_MOC_Dashboard.md`) — Para identificar el estado actual del Roadmap y el próximo paso a ejecutar.
2. `Proyecto_Cocina_IA/01_Spec_Tecnico_y_Funcional.md` — Para respetar la arquitectura técnica, los esquemas de base de datos y la funcionalidad de cada vista.
3. `Proyecto_Cocina_IA/02_Perfil_Clinico_y_Nutricional.md` — Para tener presentes las directrices clínicas, metas de déficit calórico (1.700 kcal Gonzalo / 1.350-1.400 kcal Marta), micronutrientes, restricciones de absorción de hierro y reglas antirreflujo.

---

## 2. Desarrollo Autónomo y Código Íntegro
- **Cero programación manual por parte del usuario:** El usuario no toca ni pega código. El agente crea, actualiza y edita directamente todos los archivos en la raíz del proyecto y sus subcarpetas.
- **Prohibido truncar código:** No usar comentarios del tipo `// resto del código igual`, `/* ... */` o snippets incompletos. Los archivos se escriben completos y funcionales.

---

## 3. Inyección del System Prompt Clínico
- El módulo `ai_engine.py` (cuando se desarrolle en la Fase 3) debe leer de forma nativa y directa el archivo `Proyecto_Cocina_IA/02_Perfil_Clinico_y_Nutricional.md` para inyectarlo como `system_instruction` permanente en el modelo `gemini-3.6-flash` (principal, con respaldo automático a `gemini-3.5-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite`), junto con el estado del inventario y recetas.

---

## 4. Ejecución Estricta del Roadmap
- Avanzar estrictamente paso a paso según el Roadmap definido en el MOC Dashboard.
- **Nunca avanzar al siguiente paso** sin la confirmación y validación explícita del usuario.
- En cada paso, cumplir únicamente el alcance asignado sin adelantarse a fases futuras.

---

## 5. Protocolo de Cierre de Sesión ("Cerramos sesión")
Cuando el usuario indique "Cerramos sesión" o frase equivalente:
1. Actualizar el bloque `## ESTADO ACTUAL` en `Proyecto_Cocina_IA/00_MOC_Dashboard.md.md`:
   - Fase actual.
   - Último avance completado.
   - Archivos de código creados o modificados.
   - Próximo paso exacto a realizar en la siguiente sesión.
2. Marcar las casillas `[x]` de los pasos del Roadmap completados.
3. Crear un archivo de log de sesión con la fecha del día en `Proyecto_Cocina_IA/sesiones/` (ej. `YYYY-MM-DD_sesion.md`) detallando:
   - Pasos completados.
   - Decisiones técnicas tomadas.
   - Estado de los archivos.
   - Instrucción precisa con la que retomar la próxima vez.
