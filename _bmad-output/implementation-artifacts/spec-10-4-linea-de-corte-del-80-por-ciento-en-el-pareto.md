---
title: 'Story 10.4: Línea de corte del 80% en el Pareto'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
baseline_commit: 'd926991'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La gráfica Pareto interactiva (`chart-canvas.component.ts`) no marca visualmente dónde el `% acumulado` cruza el 80% — el SVG que reemplazó (`table_builder.py::_pareto_chart_lines`) sí lo hacía con una línea horizontal punteada (`_ax2.axhline(80, ...)`) en el eje secundario.

**Approach:** Agregar la librería `chartjs-plugin-annotation` (compatible con Chart.js 4) y configurar una anotación de tipo línea horizontal en `y1=80` con la etiqueta "80%", replicando la referencia visual que ya existía en el SVG — no una nueva decisión de diseño, sino la migración de una que ya estaba. Usa el color de énfasis existente del componente (mismo qué usará la Story 10.5 para el resto de la paleta; por ahora un color fijo razonable, ya que 10.5 es quien conecta todo a los design tokens).

</frozen-after-approval>

## Implementation Notes

- Dependencia nueva: `chartjs-plugin-annotation@3.1.0` (compatible con Chart.js 4), agregada con `yarn add`.
- `chart-canvas.component.ts`: registrado `annotationPlugin` junto a `registerables`; agregada anotación `line80` (tipo `line`, `yMin`/`yMax: 80`, `yScaleID: 'y1'`, con etiqueta "80%") en `plugins.annotation.annotations`. Color fijo (`#888888`) por ahora — la Story 10.5 conecta todos los colores del componente a los design tokens.
- Test nuevo: verifica que la anotación `line80` existe con `yMin`/`yMax: 80` sobre el eje `y1`.
- `yarn build` limpio; 9/9 tests en verde.
- Revisión (blind-hunter): 8 hallazgos, 6 sobreviven, parchados en el mismo pase:
  - `chartAriaLabel` actualizado para mencionar la referencia del 80%.
  - `y1.max` subido de `100` a `105`, igualando el `set_ylim(0, 105)` del SVG original — evita que la etiqueta "80%" quede pegada/recortada contra el borde del eje.
  - Color `#888888` extraído a la constante `REFERENCE_LINE_COLOR`, con un comentario `TODO(Story 10.5)` marcando el contraste insuficiente (blanco sobre gris ≈3.5:1, bajo el mínimo WCAG AA de 4.5:1) para cuando esa historia conecte los colores a los tokens.
  - Test nuevo verifica también `label.display`/`label.content` de la anotación, no solo `yMin`/`yMax`/`yScaleID`.
  - Test nuevo verifica que la anotación sobrevive al camino de `update()` con datos distintos, no solo en la creación inicial.
  - El cast `as any` del test se reemplazó por el tipo real `LineAnnotationOptions` de `chartjs-plugin-annotation`.
  - Rechazado: caso `records=[]`/todo-NaN es inalcanzable con el único caller real (mismo argumento que en Stories 10.1/10.2 — el `@if` de `analysis-dashboard` ya filtra eso).

## Review Triage Log

| # | Hallazgo | Veredicto | Evidencia |
|---|----------|-----------|-----------|
| 1 | `chartAriaLabel` no menciona la línea del 80% | low | Real: único canal accesible del canvas. Patch. |
| 2 | Test no verifica texto/`display` de la etiqueta de la anotación | low | Real gap de cobertura. Patch. |
| 3 | `label: 'end'` con solo 20 de margen (`y1.max: 100`) podría recortarse | medium | Real: el SVG original usaba `set_ylim(0, 105)` explícitamente por esta razón. Patch (`y1.max: 105`). |
| 4 | `'#888888'` repetido sin constante nombrada | low | Real, friction anticipada para la Story 10.5. Patch. |
| 5 | Contraste blanco-sobre-gris ~3.5:1, bajo WCAG AA, sin nota para el follow-up | low | Real pero el color es un placeholder deliberado (10.5 lo reemplaza) — se agregó comentario `TODO` en vez de resolver el color ahora. Patch (documentación). |
| 6 | Test castea `as any` en vez de usar los tipos reales del plugin | low | Real mejora de tipado; se confirmó que `LineAnnotationOptions` compila. Patch. |
| 7 | Sin test de que la anotación sobrevive al `update()` con datos distintos | low | Real gap de cobertura, mismo patrón que Story 10.3. Patch. |
| 8 | Sin test para `records=[]`/todo-NaN | false | Inalcanzable: el `@if` de `analysis-dashboard.component.html` nunca monta `chart-canvas` con `records` vacío. |

