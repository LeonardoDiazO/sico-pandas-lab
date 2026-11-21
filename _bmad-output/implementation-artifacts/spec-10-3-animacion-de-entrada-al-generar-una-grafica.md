---
title: 'Story 10.3: Animación de entrada al generar una gráfica'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
baseline_commit: '2d3fbc9'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Chart.js ya anima por defecto (duración por defecto 1000ms), pero eso es un valor implícito de la librería, no una decisión explícita — el AC pide "menos de 1 segundo" y el comportamiento actual (exactamente 1000ms) queda en el límite, además de no estar documentado ni protegido de un cambio de default en una futura versión de Chart.js.

**Approach:** Configurar `animation: { duration, easing }` explícitamente en las opciones del chart (duración claramente bajo 1 segundo). El resto del AC ("si regenero la misma gráfica, la animación se repite sin duplicar elementos") ya lo cumple la estructura actual de `render()`: reutiliza la misma instancia de `Chart` vía `chart.update()` en vez de crear una nueva cada vez, y Chart.js anima la transición de valores en cada `update()` igual que en la creación inicial — no requiere cambio de lógica, solo la config explícita de duración/easing.

</frozen-after-approval>

## Implementation Notes

- Único archivo tocado: `chart-canvas.component.ts` — se agregó `animation: { duration: 700, easing: 'easeOutQuart' }` a las opciones del chart. `render()` no cambió de estructura (sigue reutilizando la misma instancia de `Chart` vía `update()`), así que la animación aplica tanto a la creación inicial como a cada regeneración.
- Se agregaron 2 tests: uno verifica que `duration < 1000` (no confiar en el default de Chart.js), otro verifica que regenerar con datos distintos reutiliza la misma instancia de `Chart` (`Chart.getChart(canvas)` antes/después es el mismo objeto) — cubre directamente el AC "sin duplicar elementos visuales".
- `yarn build` limpio; 7/7 tests en verde (incluye los de las Stories 10.1/10.2).
- Revisión (blind-hunter): 7 hallazgos, 4 sobreviven, parchados en el mismo pase:
  - `prefers-reduced-motion` no se manejaba (patrón ya establecido en el repo vía CSS, pero inaplicable a una animación de canvas — se agregó `prefersReducedMotion()` con `window.matchMedia`, duración cae a `0` si aplica).
  - `duration`/`easing` extraídos a una constante nombrada (`ENTRY_ANIMATION_DURATION_MS`) y el test ahora afirma el valor exacto (`700`), no solo el rango `<1000`.
  - Test nuevo cubriendo `easeOutQuart` explícitamente.
  - El test de "reutiliza la misma instancia" ahora también verifica la duración después del `update()`, no solo en la creación inicial.
  - **Hallazgo imprevisto durante el parcheo:** ChromeHeadless (el navegador de este suite de pruebas) reporta `prefers-reduced-motion: reduce` como `true` por defecto — sin aislar `window.matchMedia` en los tests, los dos tests de duración fallaban (`0` en vez de `700`). Se agregó un mock por defecto (`matches: false`) en `beforeEach`, restaurado en `afterEach`, para que cada test sea determinista sin depender del comportamiento del navegador headless.

## Review Triage Log

| # | Hallazgo | Veredicto | Evidencia |
|---|----------|-----------|-----------|
| 1 | Sin manejo de `prefers-reduced-motion` | medium | Real: convención ya establecida en el repo (CSS en `no-code-home`/`column-classification`), pero una animación de canvas no la hereda. Patch. |
| 2 | Test de duración solo verifica `<1000`, no el valor exacto (700) | low | Real gap de precisión de test — una regresión a 950ms pasaría igual. Patch (assert exacto). |
| 3 | Sin test para `easing: 'easeOutQuart'` | low | Real gap de cobertura. Patch (assert agregado). |
| 4 | El test de "misma instancia" no revisa la animación tras `update()` | low | Real: la nota de implementación afirma que aplica también en regeneración, pero nada lo probaba. Patch (assert agregado al mismo test). |
| 5 | `700`/`'easeOutQuart'` como literales mágicos sin constante nombrada | low | Rechazado: sin daño concreto nombrado, un solo archivo, sin duplicación real. (Se nombró la constante de todas formas como efecto colateral del fix #1, no como corrección independiente). |
| 6 | El comentario no explica por qué se fija `easeOutQuart` (ya es el default) | low | Rechazado: nitpick de documentación, sin riesgo funcional. |
| 7 | `sprint-status.yaml`/frontmatter seguían en `in-progress` pese a estar funcionalmente terminado | false | No es un defecto: `step-oneshot.md` actualiza el status en la sección "Finalize Spec", posterior a esta clasificación — es la secuencia normal del flujo, no un olvido. |

