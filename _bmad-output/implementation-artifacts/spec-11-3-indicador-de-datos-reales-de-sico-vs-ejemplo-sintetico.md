---
title: 'Story 11.3: Indicador de datos reales de SICO vs. ejemplo sintético'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: []
baseline_commit: 'b8cedeb'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `data_context.resolve_context(lesson_id, learner_profile)` ya decide, por lección, si hay datos reales de SICO disponibles para sustituir en el contenido (`context is not None`) — pero esa decisión solo se calcula hoy al pedir el detalle de UNA lección (`GET /api/guided/lessons/<id>`), nunca en el listado (`GET /api/guided/lessons`) que alimenta el mapa de `guided-home` (Story 11.1, ya implementada). El listado tampoco recibe el perfil de la sesión — ni siquiera podría calcularlo hoy.

**Approach:** Extender `content.list_lessons(learner_profile=None)` para que, por cada lección, calcule también `usa_datos_reales: bool` vía `data_context.resolve_context(lesson["id"], learner_profile) is not None` — reutilizando la función ya existente, sin lógica nueva de negocio. `routes.py::lessons()` obtiene el perfil de la sesión igual que ya hace `lesson()` (`_manager().get_known_profile(_session_id())`) y lo pasa. En el frontend, cada tarjeta del mapa (`guided-home.component.html`, ya rediseñado en la Story 11.1) muestra un indicador corto: "📊 Con tus datos de SICO" o "🧪 Ejemplo". Aplica a las 6 lecciones por igual — las 3 que no están en `LESSON_ROLES` (`00-python-desde-cero`, `02-filtrar-ordenar`, `04-combinar-tablas`) siempre calculan `False` (nunca sustituyen), lo cual es correcto: nunca usan datos reales, con o sin perfil.

## Boundaries & Constraints

**Always:**
- Reutilizar `data_context.resolve_context()` tal cual — no se duplica ni se reimplementa su lógica de elegibilidad (`LESSON_ROLES`) en el listado.
- El perfil de sesión se obtiene con el mismo patrón ya usado en `lesson()` (`_manager().get_known_profile(_session_id())`) — sin sesión o sin perfil, todas las lecciones devuelven `usa_datos_reales: false` (comportamiento ya soportado por `resolve_context`, que trata `learner_profile=None` como "sin datos reales").
- El campo nuevo se agrega al dict de cada lección en `list_lessons()`, sin tocar la forma de `get_lesson()` (que ya tiene su propio mecanismo de sustitución completo).
- Coordina con el marcado de tarjeta que ya introdujo la Story 11.1 (`.lesson-card`, `.badge`) — el indicador nuevo va junto al contenido existente, no rehace el layout del nodo/mapa.

**Never:**
- No tocar `get_lesson()`, `challenges.py`, ni el flujo de sustitución de texto (`substitute_identifiers`) — todo eso ya funciona y no cambia.
- No cambiar `LESSON_ROLES` ni la lógica de elegibilidad de `resolve_context()` — esta historia solo expone un dato que ya se calculaba en otro endpoint, no cambia cuándo algo cuenta como "datos reales".

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sesión sin perfil (nunca subió Excel) | `learner_profile=None` | Las 6 lecciones devuelven `usa_datos_reales: false` | N/A |
| Sesión con perfil, lección elegible (`01-fundamentos`) y perfil suficiente | `resolve_context(...)` devuelve contexto | `usa_datos_reales: true` para esa lección | N/A |
| Sesión con perfil, pero perfil insuficiente para esa lección (faltan columnas del rol) | `resolve_context(...)` devuelve `None` | `usa_datos_reales: false` | N/A |
| Lección fuera de `LESSON_ROLES` (ej. `00-python-desde-cero`) | Cualquier perfil, incluso completo | `usa_datos_reales: false` siempre | N/A |
| Sin header de sesión (`X-Session-Id` ausente) | `_session_id()` devuelve `"anonymous"` | Mismo comportamiento que sesión sin perfil (`get_known_profile` devuelve `None` para una sesión desconocida) | Ya cubierto por `get_known_profile`, sin cambio |

</frozen-after-approval>

## Code Map

- `backend/app/guided/content.py::list_lessons()` -- cambiar firma a `list_lessons(learner_profile=None)`; por cada lección, agregar `"usa_datos_reales": data_context.resolve_context(l["id"], learner_profile) is not None` al dict devuelto. Requiere `from app.guided import data_context` a nivel de módulo (hoy solo se importa dentro de `get_lesson()`, de forma local).
- `backend/app/guided/routes.py::lessons()` -- obtener `profile = _manager().get_known_profile(_session_id())` (mismo patrón que `lesson()`, línea 33) y pasarlo: `content.list_lessons(learner_profile=profile)`.
- `frontend/src/app/models/api.models.ts::LessonSummary` -- agregar `usa_datos_reales: boolean`.
- `frontend/src/app/guided/guided-home/guided-home.component.html` -- dentro de `.lesson-card` (dentro del `<a>`, junto al `<p>` de resumen ya existente), agregar el indicador: `📊 Con tus datos de SICO` si `item.lesson.usa_datos_reales`, `🧪 Ejemplo` si no.
- `frontend/src/app/guided/guided-home/guided-home.component.scss` -- estilo del nuevo indicador (`.data-source`), reutilizando tokens ya presentes en el archivo tras la Story 11.1 (`--ok`/`--ink-muted` o similar), sin introducir hex nuevo.
- `backend/tests/test_guided_routes.py` (o el archivo de tests de guided existente) -- verificar `usa_datos_reales` en la respuesta del listado, para los 5 escenarios de la matriz I/O.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/guided/content.py` -- `list_lessons(learner_profile=None)` calcula `usa_datos_reales` por lección -- núcleo del dato nuevo
- [ ] `backend/app/guided/routes.py` -- pasar el perfil de sesión al listado -- conecta el dato con la sesión real
- [ ] `frontend/src/app/models/api.models.ts` -- agregar campo al tipo -- necesario para que TypeScript lo reconozca
- [ ] `frontend/src/app/guided/guided-home/guided-home.component.html/.scss` -- indicador visible por tarjeta -- UI de la historia
- [ ] Tests backend de los 5 escenarios de la matriz I/O -- cubre la lógica nueva de `list_lessons`

**Acceptance Criteria:**
- Given que ya subí un Excel con columnas suficientes para la Lección 1, when veo el mapa de lecciones, then la tarjeta de "1. Fundamentos" indica "Con tus datos de SICO".
- Given que nunca subí datos, when veo el mapa, then las 6 tarjetas indican "Ejemplo".
- Given la Lección 0 ("Python desde cero", fuera de `LESSON_ROLES`), when veo el mapa con cualquier perfil, then esa tarjeta siempre indica "Ejemplo".
- Given que hago un pedido sin header `X-Session-Id`, when el backend arma el listado, then no lanza error — todas las lecciones devuelven `usa_datos_reales: false`.

## Implementation Notes

- `content.py::list_lessons(learner_profile=None)` agrega `usa_datos_reales` por lección reutilizando `data_context.resolve_context()` tal cual — sin lógica nueva de elegibilidad. `routes.py::lessons()` obtiene el perfil de sesión con el mismo patrón ya usado en `lesson()`.
- `LessonSummary` (frontend) agrega `usa_datos_reales: boolean`. `guided-home.component.html` muestra el indicador dentro de cada `.lesson-card`.
- Tests backend nuevos cubren los 5 escenarios de la matriz I/O (`test_guided_routes.py`): sin perfil, sin header de sesión, perfil suficiente, perfil insuficiente (numérico) y perfil insuficiente (sin columna categórica).
- `yarn build`/`python -m pytest` limpios (434 backend, 9 frontend en `guided-home`).
- Revisión (blind-hunter, edge-case-hunter: sin hallazgos; verification-gap: sin gaps, 1 hallazgo secundario): 6 hallazgos en total, 4 sobreviven, parchados en el mismo pase; 2 rechazados.
  - Import local muerto de `data_context` dentro de `get_lesson()` eliminado (ya quedó como import de módulo tras esta historia).
  - `.data-source` usaba `--ok` (verde de "completada") para ambas ramas del indicador — "Ejemplo" ahora usa `--ink-muted` (neutro), "Con tus datos de SICO" mantiene `--ok`.
  - Emoji del indicador envuelto en `<span aria-hidden="true">` — mismo patrón que `.node-marker` de la Story 11.1, evita que un lector de pantalla anuncie el nombre del emoji antes del texto.
  - Test nuevo para perfil sin ninguna columna categórica (antes solo se cubría "perfil con una sola columna numérica").
  - Rechazado: el indicador no se expone también en `get_lesson()`/vista de detalle de lección — el Intent y el Approach de esta spec limitan explícitamente el alcance a la tarjeta del mapa (`guided-home`), no a la vista de lección.
  - Rechazado: `resolve_context()` se recalcula por separado para `01-fundamentos` y `03-agrupar` pese a compartir el mismo `LESSON_ROLES` — optimización real pero de bajo impacto (6 lecciones, request poco frecuente); memoizar agregaría más complejidad de la que amerita.

## Spec Change Log

## Review Triage Log

| # | Fuente | Hallazgo | Veredicto | Evidencia |
|---|--------|----------|-----------|-----------|
| 1 | blind-hunter | Import local muerto de `data_context` en `get_lesson()` | low | Real, trivial. Patch (eliminado). |
| 2 | blind-hunter + verification-gap | `.data-source` sin diferenciación visual real vs. sintético (mismo `--ok` verde en ambas ramas) | medium | Real y visible, coincide entre dos capas independientes. Patch (`--ink-muted` para "Ejemplo"). |
| 3 | blind-hunter | Indicador no se expone en `get_lesson()`/vista de detalle | — | Rechazado — fuera de alcance explícito según el Intent/Approach de esta misma spec (solo la tarjeta del mapa). |
| 4 | blind-hunter | Emoji inline sin `aria-hidden`, inconsistente con el patrón ya usado en `.node-marker` | low | Real, mismo patrón ya establecido en la Story 11.1. Patch. |
| 5 | blind-hunter | `resolve_context()` recalculado por separado para lecciones con el mismo `LESSON_ROLES` | low | Real pero bajo impacto (6 lecciones). Rechazado — memoizar no vale la complejidad. |
| 6 | blind-hunter | Sin test de perfil sin columna categórica (solo se cubría "num2 insuficiente") | low | Real gap de cobertura, fix trivial. Patch (test nuevo agregado). |
| — | edge-case-hunter | Sin hallazgos | — | — |
| — | verification-gap | Sin gaps de verificación (todas las ramas cambiadas tienen test que fallaría si se rompen) | — | — |

## Verification

**Commands:**
- `cd backend && python -m pytest` -- expected: todas las pruebas en verde, incluidas las nuevas de `list_lessons`.
- `cd frontend && yarn build` -- expected: compila sin errores (campo nuevo tipado).
- `cd frontend && yarn test --watch=false --browsers=ChromeHeadless --include="src/app/guided/guided-home/**/*.spec.ts"` -- expected: tests existentes y nuevos en verde.

**Manual checks (if no CLI):**
- Con un Excel real cargado en el panel de datos, entrar a `/guiado` y confirmar que la tarjeta de la Lección 1 dice "Con tus datos de SICO" y la Lección 0 dice "Ejemplo".
