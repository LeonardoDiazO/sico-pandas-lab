---
title: 'Story 10.2: Ver tooltip con valor exacto en las gráficas'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
baseline_commit: '3b74fce'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El chart Pareto interactivo de la Story 10.1 (`chart-canvas.component.ts`) ya renderiza con Chart.js, pero usa el tooltip por defecto de la librería: solo muestra el valor del dataset sobre el que está el mouse (barra O línea, no ambos juntos), sin el `% acumulado` en la misma vista y sin formato de miles.

**Approach:** Configurar `interaction: { mode: 'index', intersect: false }` para que al pasar el mouse sobre una barra el tooltip agregue también el valor de la línea de `% acumulado` en ese mismo punto, y personalizar `tooltip.callbacks.label` para formatear el valor con separador de miles y añadir el sufijo `%` a la línea acumulada. El soporte táctil ("tocar la barra") ya lo cubre Chart.js de fábrica (`events` por defecto incluye `touchstart`/`touchmove`) — no requiere código nuevo, solo verificación manual.

</frozen-after-approval>

## Implementation Notes

- Único archivo tocado: `frontend/src/app/shared/chart-canvas/chart-canvas.component.ts`. Se agregó `interaction: { mode: 'index', intersect: false }` (agrupa barra + línea en un solo tooltip por categoría) y `plugins.tooltip.callbacks.label` (formatea el valor con separador de miles `es-CO` y agrega `%` a la línea acumulada; `sin dato` cuando el valor es `null`/`NaN`, coherente con el fix de la Story 10.1 que usa `NaN` para valores no parseables).
- Soporte táctil: no se tocó nada — Chart.js trae `touchstart`/`touchmove` en su lista de `events` por defecto, así que "tocar la barra" ya funciona sin configuración adicional. Queda pendiente de verificación manual (no puedo probar touch real desde este entorno).
- Fix de tipos durante el build: `context.parsed.y` es `number | null` en los tipos de Chart.js 4 — se agregó el chequeo `value === null` junto al `!Number.isFinite(value)` ya existente.
- `yarn build` limpio; specs existentes de `chart-canvas`/`analysis-dashboard` (4/4) siguen en verde — no se agregó spec nuevo para el callback del tooltip (revisar si Blind Hunter lo señala).
- Revisión (blind-hunter) encontró 8 hallazgos; sobrevivieron 2 (agrupados en uno solo de formato + uno de cobertura), parchados en el mismo pase:
  - `formatTooltipLabel()` extraído como método privado testeable; ahora usa `looksLikeMoney(valueKey)` (ya exportado de `money-format.ts`) para anteponer `"$ "` en columnas de dinero (antes se perdía el prefijo al reformatear el número ya parseado), y para columnas no-dinero deja hasta 2 decimales en vez de redondear siempre a entero (el AC pide "valor exacto", no truncar precisión de una métrica tipo promedio).
  - Se agregó un test nuevo (`chart-canvas.component.spec.ts`) que cubre las 4 ramas de `formatTooltipLabel`: dinero, no-dinero con decimales, línea `% acumulado`, y el placeholder `sin dato`.

## Review Triage Log

| # | Hallazgo | Veredicto | Evidencia |
|---|----------|-----------|-----------|
| 1 | Sin test para el callback del tooltip | medium | Real gap de cobertura; corregido agregando test dedicado a `formatTooltipLabel`. Patch. |
| 2 | Prefijo "$" se pierde en el tooltip para columnas de dinero (inconsistente con la tabla al lado) | medium | Real y visible: la tabla HTML del mismo bloque muestra "$ 1.200" y el tooltip mostraba "1.200" sin signo. Corregido con `looksLikeMoney`. Patch (agrupado con #3, misma causa raíz: formato de número sin distinguir tipo de columna). |
| 3 | `Math.round()` trunca decimales incluso en métricas no-dinero, contradice "valor exacto" | medium | Real: una columna tipo promedio con `1234.56` se mostraba como `1.235`. Corregido: no-dinero conserva hasta 2 decimales. Patch (mismo grupo que #2). |
| 4 | Sin ruta de teclado para disparar el tooltip (accesibilidad) | low | Rechazado: poco probable en uso cotidiano de esta herramienta interna (NFR ya acepta nivel básico, sin WCAG formal); el fix real (manejo de foco/teclado en un `<canvas>`) es mucho más que una corrección simple. |
| 5 | Soporte táctil no verificado, solo declarado por comentario | — | No es un defecto de código — ya estaba declarado como pendiente de verificación manual en las notas de implementación; depende de un comportamiento de fábrica de Chart.js, no de código nuevo. Sin acción. |
| 6 | `chartAriaLabel` no menciona la nueva capacidad de tooltip | low | Rechazado: un aria-label describe qué es el gráfico, no cómo interactuar con él — beneficio marginal, no es una convención esperada. |
| 7 | Distinguir línea vs. barra por `dataset.type === 'line'` es frágil para futuras historias (10.4/10.5) | low | Rechazado: hoy solo hay 2 datasets, sin ambigüedad — preocupación especulativa sobre historias futuras, no alcanzable con el código actual. |
| 8 | Sin supresión de la línea `% acumulado` cuando un bloque no es Pareto | false | Refutado: todo bloque del tablero automático se genera vía `build_summary_code` (`analysis_catalog.py::build_catalog`), que siempre calcula `% acumulado` — no existe un bloque "no-Pareto" alcanzable hoy. |

