# Epic 11 Context: Progreso y feedback en el módulo guiado

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Quien avanza por las 6 lecciones del módulo guiado hoy solo ve una lista vertical plana con un ✓ junto a lo completado, sin sensación real de progreso ni reacción distinta al superar un reto (el resultado se ve igual que el de cualquier celda ejecutada sin más), y sin saber si está trabajando con sus propios datos de SICO o con un ejemplo sintético. Esta épica introduce un mapa de lecciones tipo camino con 3 estados visuales claros (completada, actual, bloqueada), una reacción visual distinta y contextual al superar un reto verificado en servidor, y un indicador por lección de "tus datos" vs. "ejemplo" — todo como trabajo de frontend puro, sin lógica nueva de backend.

## Stories

- Story 11.1: Ver el progreso de las 6 lecciones como un mapa
- Story 11.2: Feedback distinto al superar un reto
- Story 11.3: Indicador de datos reales de SICO vs. ejemplo sintético

## Requirements & Constraints

- Un reto que pasa la validación del servidor debe reaccionar de forma visualmente distinta a un reto que simplemente ejecutó sin error (no basta con que el código corra).
- Los 3 estados del mapa de lecciones (completada, actual, bloqueada) deben distinguirse sin necesidad de leer texto; la lección "actual" es siempre la primera no completada de la secuencia.
- Una lección bloqueada por prerequisito no cumplido debe ser no-clickeable o mostrar un aviso claro, no comportarse como una lección normal.
- Cada tarjeta de lección debe indicar si usa datos reales de SICO o un ejemplo sintético, usando el dato que el backend ya calcula (sin requerir trabajo nuevo de backend para obtenerlo).
- Sin objetivo formal de tiempo de respuesta ni de accesibilidad WCAG, pero se exige contraste y navegación por teclado razonables en los nuevos elementos visuales (mapa, tooltips).
- Si algo del nuevo feedback visual falla, debe degradar a un estado claro, nunca a pantalla en blanco o comportamiento roto.
- El pulido visual (micro-interacciones, estados vacíos con más carácter, transiciones consistentes) es criterio de aceptación exigido en las historias de esta épica, no trabajo opcional sin dueño.
- Explícitamente fuera de alcance: racha o gamificación de sesión (requiere lógica de tiempo/sesión inexistente y una decisión de diseño no resuelta) — candidata a una épica futura, no bloquea esta.

## Technical Decisions

- El listado de lecciones de `guided-home` hoy solo devuelve `{id, title, summary}` — estático, igual para cualquier sesión. La resolución real vs. sintético (`data_context.py`) solo corre hoy al pedir una lección individual o revisar un reto, nunca en el listado; Story 11.3 necesita ese cálculo también por lección en el contexto del mapa (aunque sea consultando el detalle de cada una).
- "Lección completada" es puramente de frontend: una lista de ids en localStorage vía el servicio de perfil de usuario, sin contraparte en backend. El estado "actual" del mapa (Story 11.1) se deriva igual, en cliente, como la primera lección de la secuencia fija ausente de esa lista — no existe ni debe inventarse un flag de backend.
- No hay concepto de prerequisito o bloqueo formal ni en backend ni en el contenido: las 6 lecciones son una lista fija y secuencial; el backend solo expone id/título de la siguiente para navegar hacia adelante. El "bloqueo por prerequisito" de Story 11.1 es regla de negocio nueva puramente de frontend (p. ej. toda lección posterior a la "actual" se trata como bloqueada).
- El endpoint de revisión de reto ya distingue "código corrió sin error" de "reto superado": devuelve, junto a los campos normales de resultado de celda, un veredicto con `passed` (booleano) y mensaje — `null` solo si el código falló antes de poder revisarse. Story 11.2 se apoya en esa señal ya existente; el trabajo es de reacción visual en frontend, no de agregar la señal.
- El resultado de una celda de reto se renderiza hoy vía el mismo componente intermedio que envuelve al de resultado de celda en toda ejecución (editor + acciones + resultado), con un aviso textual de color ya distinto debajo al revisar el reto — pero estático, sin transición propia del acierto. El nuevo feedback de Story 11.2 debe envolver ese componente intermedio (sin reemplazarlo ni reemplazar el de resultado de celda), agregando la transición y el micro-mensaje que hoy faltan.
- El tour guiado de la lección referencia selectores CSS concretos de sus secciones (incluida la del reto); cualquier cambio estructural de Story 11.2 ahí debe conservar esos selectores o actualizar el tour en el mismo cambio.
- Ni la vista de inicio del módulo guiado ni la de lección usan hoy ningún token de color del stylesheet global (`--ink`, `--brand`, `--ok`, `--bad`, `--warn`, etc.) — todos sus colores están hardcodeados en hex. Cualquier color nuevo de esta épica (estados del mapa, feedback de reto superado, badge de datos reales/sintéticos) debe leerse de esos tokens, migrando también los colores existentes que se toquen.

## UX & Interaction Patterns

- `guided-home` pasa de lista vertical a un mapa/camino de 6 lecciones conectadas visualmente, con estilo distinguible para completada, actual y bloqueada.
- Al superar un reto en `guided-lesson`, aparece una transición y un micro-mensaje contextual, visualmente distinto del resultado crudo de ejecutar una celda cualquiera; si el código corre sin error pero no cumple el reto, se ve el resultado normal, sin ese feedback especial.
- Cada tarjeta de lección muestra un indicador corto ("tus datos" / "ejemplo") de si trabaja con datos reales de SICO o con el ejemplo sintético de esa lección.

## Cross-Story Dependencies

- Story 11.1 y Story 11.3 modifican la misma superficie (las tarjetas de lección de `guided-home`); conviene implementarlas de forma coordinada para no rehacer el marcado de las tarjetas dos veces.
- Story 11.2 es independiente de las otras dos: solo toca `guided-lesson` y el flujo de revisión de reto, no el mapa de `guided-home`.
- Ninguna dependencia entre esta épica y la Épica 10 (gráficos interactivos del módulo sin código); ambas asumen que las épicas 3 a 8 ya implementadas siguen intactas.
