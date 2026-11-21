---
title: 'Story 11.1: Ver el progreso de las 6 lecciones como un mapa'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: []
baseline_commit: '899032a'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `guided-home.component` muestra las 6 lecciones como una lista vertical plana (`.lesson-card`), cada una con un ✓ si está completa — sin mapa de progreso, sin distinguir cuál es "la actual", y sin ningún concepto de bloqueo. `isComplete()` es el único estado hoy (booleano, vía `localStorage` a través de `UserProfileService`); no existe backend para "actual" ni "bloqueada" — ambos deben derivarse en el frontend.

**Approach:** Transformar la lista en un camino vertical: línea conectora + nodo por lección, con 3 estados visuales derivados en el componente (no en el backend): `completada` (ya en la lista de `localStorage`), `actual` (la primera lección de la secuencia fija que NO está completa), `bloqueada` (cualquier lección posterior a la actual). Las bloqueadas no son clickeables (sin `routerLink`, con indicación visual de candado) — AC explícito: "no clickeable o con aviso claro". Colores migrados a los design tokens compartidos (`--ok`, `--brand`, `--ink-muted`, `--border`), reemplazando el hex hardcodeado que tiene hoy este archivo.

## Boundaries & Constraints

**Always:**
- El orden de las lecciones es el que ya devuelve el backend (`content.list_lessons()`, orden fijo del arreglo `LESSONS`) — no se reordena ni se pide un campo de secuencia nuevo.
- "Actual" = primera lección (en ese orden) para la que `isComplete(id)` es `false`. Si todas están completas, ninguna lección se marca como "actual" (todas quedan en estado completada).
- "Bloqueada" = cualquier lección cuyo índice sea mayor al de la "actual". Antes de la actual (inclusive), nunca bloqueada.
- Es una regla de negocio puramente de frontend — no se agrega ningún campo de backend ni se persiste el bloqueo.
- El indicador de datos reales/sintéticos por lección (Story 11.3) NO es parte de esta historia — se coordina para no rehacer el marcado de la tarjeta dos veces, pero esta historia entrega valor completo sin él.

**Never:**
- No tocar `guided-lesson.component` (esa es la Story 11.2, ya hecha) ni el backend (`content.py`, `data_context.py`) — nada de esto requiere un campo nuevo del servidor.
- No implementar racha/gamificación de sesión (explícitamente fuera de alcance de toda la Épica 11).
- No convertir el bloqueo en algo real/de seguridad (un usuario que edite la URL directamente a `/guiado/05-graficas` sin haber completado las anteriores no debe ser bloqueado por el backend — el bloqueo es solo de descubrimiento/UX en el mapa, no una restricción de acceso).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Primera visita | Ninguna lección completa | Lección 0 = actual; lecciones 1-5 = bloqueadas | N/A |
| Progreso a mitad | Lecciones 0-2 completas | Lección 3 = actual; 0-2 = completadas; 4-5 = bloqueadas | N/A |
| Curso terminado | Las 6 completas | Las 6 = completadas; ninguna actual ni bloqueada | N/A |
| Backend de lecciones falla | `guided.listLessons()` error | Se mantiene el manejo de error ya existente (`loading = false`, lista vacía) | Ya cubierto, sin cambios |
| Click en lección bloqueada | Usuario intenta navegar | No navega (sin `routerLink` activo) | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/app/guided/guided-home/guided-home.component.ts` -- agregar un getter/método que derive `{lesson, state}[]` (`state: 'completada' | 'actual' | 'bloqueada'`) a partir de `lessons` + `isComplete()`, en el orden ya devuelto por el backend. `isComplete(lessonId)` existente se reutiliza tal cual.
- `frontend/src/app/guided/guided-home/guided-home.component.html` -- reemplazar `.lesson-list`/`.lesson-card` por el mapa: contenedor de camino vertical, un nodo+tarjeta por lección, `[routerLink]` condicional (solo si no está bloqueada), indicador visual por estado (✓ completada, resaltado actual, 🔒 bloqueada).
- `frontend/src/app/guided/guided-home/guided-home.component.scss` -- rediseño del `.lesson-card` a nodo de camino (línea conectora entre tarjetas, ej. `::before`/`::after` o un contenedor con borde izquierdo) + migración de todo el hex hardcodeado a tokens (`--ink`, `--ink-muted`, `--brand`, `--brand-soft`, `--ok`, `--ok-soft`, `--border`).
- `frontend/src/app/models/api.models.ts` -- sin cambios; `LessonSummary` ya tiene lo necesario (`id`, `title`, `summary`).
- `backend/app/guided/*` -- sin cambios (regla de bloqueo es puramente de frontend, ver Boundaries).

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/app/guided/guided-home/guided-home.component.ts` -- agregar derivación de estado (`completada`/`actual`/`bloqueada`) -- núcleo de la lógica de la historia
- [x] `frontend/src/app/guided/guided-home/guided-home.component.html` -- camino vertical con nodo por lección, bloqueadas sin `routerLink` -- UI de la historia
- [x] `frontend/src/app/guided/guided-home/guided-home.component.scss` -- estilos de camino + migración completa a design tokens -- UI + requisito de la épica
- [x] Test unitario de la derivación de estado (tabla del I/O Matrix) -- cubre los 3 escenarios de estado

**Acceptance Criteria:**
- Given que tengo al menos una lección completada y otras pendientes, when entro a `guided-home`, then veo las 6 lecciones conectadas visualmente con su estado distinguible sin leer texto.
- Given que ninguna lección está completa, when entro a `guided-home`, then la primera lección es "actual" y las demás están bloqueadas.
- Given que una lección está bloqueada, when intento hacer click, then no navego a ningún lado (sin `routerLink` activo en ese nodo).
- Given que las 6 lecciones están completas, when entro a `guided-home`, then ninguna se marca como bloqueada ni como actual.

## Implementation Notes

- `lessonsWithState` is a getter on `GuidedHomeComponent` (not a cached field): it recomputes on every read from `lessons` + `isComplete()`, matching the existing pattern where the template already called `isComplete()` directly. First incomplete lesson in backend order gets `'actual'`; everything after it gets `'bloqueada'`; anything before it (or itself, once complete) is `'completada'`. All complete -> no `'actual'`/`'bloqueada'` at all.
- Blocked nodes get `[routerLink]="null"` (no `href` rendered by Angular's RouterLink, so the anchor is inert -- no navigation, no keyboard activation), plus a lock emoji marker, muted styling, `cursor: not-allowed`, `aria-disabled="true"`, and a `title` tooltip as the "clear notice" the AC asks for.
- All hardcoded hex in this component's SCSS migrated to the shared tokens already defined in `frontend/src/styles.scss` (`--ink`, `--ink-muted`, `--ink-faint`, `--brand`, `--brand-ink`, `--brand-soft`, `--brand-soft-border`, `--border`, `--border-strong`, `--ok`, `--ok-soft`, `--ok-border`), each with a hex fallback (`var(--token, #hex)`) matching the pattern already used in `guided-lesson.component.scss`.
- Vertical connector line implemented via `::before` on `.lesson-node` (skipped on `:last-child`), colored with `--ok-border` once a segment leads out of a completed node.
- New unit test file `guided-home.component.spec.ts` instantiates `GuidedHomeComponent` directly with stub `GuidedService`/`UserProfileService` (no TestBed) since the derivation is pure data logic -- covers the 3 I/O Matrix scenarios (primera visita, progreso a mitad, curso terminado).
- Backend, `guided-lesson.component`, and `api.models.ts` untouched per Boundaries.

## Spec Change Log

## Review Triage Log

| # | Fuente | Hallazgo | Veredicto | Evidencia |
|---|--------|----------|-----------|-----------|
| 1 | blind-hunter | Migración de tokens cambia tonos reales (fallback ≠ token real en varios lugares) | false | Intencional: el objetivo de la historia es consistencia con la paleta de la app, no preservar el tono exacto anterior — mismo patrón ya aceptado en Stories 10.5/11.2. |
| 2 | blind-hunter | Convención de fallback inconsistente (algunos igualan al token real, otros al hex viejo) | medium | Real, verificado. Patch: fallbacks corregidos a los valores reales actuales en todo el archivo. |
| 3 | blind-hunter | Estado "completada" sin señal para lectores de pantalla (marcador `aria-hidden`) | medium | Real: la versión anterior sí tenía un `✓` no oculto; la nueva lo esconde para los 3 estados. Patch (`.sr-only`). |
| 4 | blind-hunter | Aviso de bloqueo solo vía `title`, no aparece en touch/mobile | medium | Real, verificable (los tooltips `title` requieren hover). Patch (`.lock-hint` visible). |
| 5 | blind-hunter | Test nuevo solo cubre el getter puro, no el wiring de la plantilla | medium | Real, mismo hallazgo que verification-gap (#12). Patch (test con `TestBed`). |
| 6 | blind-hunter | `lessonsWithState` sin memoizar, se recalcula en cada ciclo de detección de cambios | low | Real pero impacto insignificante a esta escala (6 lecciones, lectura de `localStorage` de un objeto diminuto). Rechazado — no vale la complejidad de memoizar. |
| 7 | blind-hunter | `LessonMapState`/`LessonMapItem` exportados sin consumidor externo | low | Rechazado: son tipos, costo cero en runtime; exportarlos es una decisión de visibilidad razonable, no un defecto. |
| 8 | blind-hunter | Sin mensaje cuando `lessons` queda vacío por error de API | — | Preexistente: la plantilla anterior tenía el mismo hueco sobre el mismo arreglo vacío. Diferido en `deferred-work.md`. |
| 9 | edge-case-hunter | Completar una lección fuera de orden (vía URL directa) la muestra "completada" en vez de "bloqueada", contradiciendo la letra literal de Boundaries | low | Real pero comportamiento defendible (mostrar el logro real es preferible a ocultarlo) y poco probable en uso cotidiano (requiere navegación por URL directa, ya que el mapa no lo permite). Rechazado, sin forzar el cambio. |
| 10 | edge-case-hunter | Mismo hallazgo framed como violación literal del texto de Boundaries | low | Mismo que #9, mismo veredicto. |
| 11 | edge-case-hunter | Estado "completada" sin señal para lectores de pantalla | medium (carried) | Duplicado de #3, mismo fix. |
| 12 | verification-gap | Sin test que proteja el mecanismo real de bloqueo (wiring `routerLink`/`aria-disabled`) | medium | Pre-verificado por la capa (evidencia: el único spec existente nunca renderiza la plantilla). Disposición filed: patch. Mismo que #5. |

**Sobreviven a patch (agrupados por causa raíz):** #2, #3+#11, #4, #5+#12 — 4 entradas independientes, todas parchadas en este mismo pase. Diferido: #8. Sin `bad_spec`/`intent_gap` — el comportamiento del código para el caso #9/#10 es una decisión defendible, no una desviación que amerite revertir y rehacer.

## Verification

**Commands:**
- `cd frontend && yarn build` -- expected: compila sin errores.
- `cd frontend && yarn test --watch=false --browsers=ChromeHeadless --include="src/app/guided/guided-home/**/*.spec.ts"` -- expected: test nuevo en verde.

**Manual checks (if no CLI):**
- Levantar la app local, entrar a `/guiado` con 0, algunas y todas las lecciones completas (se puede simular marcando/borrando `localStorage`), y confirmar visualmente el mapa y el bloqueo.

**Results (2026-09-23):**
- `cd frontend && yarn build` -- PASS, compila sin errores (único warning es un budget de `convatec-home.component.scss` preexistente, no relacionado a esta historia).
- `cd frontend && yarn test --watch=false --browsers=ChromeHeadless --include="src/app/guided/guided-home/**/*.spec.ts"` -- PASS, 3 de 3 tests en verde (los 3 escenarios del I/O Matrix).
- Corrida completa de `yarn test` (sin `--include`): 15 de 17 en verde; los 2 fallos (`App should render the brand`, `App should create the app`) son preexistentes y no relacionados -- `app-tour-overlay` no declarado en el TestBed de `app.spec.ts`, un archivo que esta historia no toca.
- Manual check en navegador no ejecutado en esta sesión (sin servidor local levantado); queda pendiente para quien revise si quiere confirmación visual además de la de build/test.

**Parcheo post-revisión (2026-09-23):**
- Fallbacks `var(--token, hex)` corregidos a los valores reales actuales de cada token en varias reglas (`--ink`, `--ink-muted`, `--border`, `--brand-soft`, `--brand-ink`) — habían quedado con el hex viejo pre-migración en algunas reglas pero no en otras, inconsistente dentro del mismo archivo.
- `.sr-only` agregado con el estado de cada lección en texto ("Lección completada."/"actual."/"bloqueada.") — antes el marcador visual era `aria-hidden` para los 3 estados y solo "actual" tenía una señal textual (el badge visible).
- `.lock-hint` visible agregado dentro de la tarjeta bloqueada — antes el único aviso era el atributo `title`, que nunca aparece en touch/mobile.
- Test nuevo con `TestBed`/`RouterTestingModule` (`describe('GuidedHomeComponent - rendered template')`) que renderiza el DOM real y verifica `routerLink`/`aria-disabled`/badge/`.sr-only`/`.lock-hint` por estado — el suite anterior solo cubría el getter puro, nunca el wiring de la plantilla que es el mecanismo real de bloqueo (hallazgo de blind-hunter + verification-gap).
- `yarn build` limpio; 8/8 tests en verde en `guided-home` (3 del getter + 5 del DOM renderizado).
