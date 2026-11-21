---
title: 'Story 10.1: Migrar el tablero automático a gráficas interactivas con datos crudos'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: []
baseline_commit: '8cf61eb6b8d0fc6aec89ef6a533130897bfa554e'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El tablero automático del módulo "sin código" (`analysis-dashboard.component`) muestra cada gráfica Pareto como una imagen SVG estática generada en el backend (matplotlib), sin ninguna interacción posible (hover, zoom, nada).

**Approach:** Añadir un nuevo componente Angular que renderiza la misma gráfica Pareto (barras de valor + línea de % acumulado en eje secundario) con Chart.js, alimentado por `result_records` — que el backend **ya expone hoy sin cambios** (confirmado por investigación: `execution.py::_capture_value()` siempre lo puebla para el DataFrame final de `build_summary_code`, y `routes.py`/`analysis_catalog.py` ya lo dejan pasar intacto hasta el frontend). Esta historia es puramente frontend y es la base técnica de las Stories 10.2-10.5 (tooltip, animación, línea del 80%, colores por token), que sí requieren esta migración ya hecha.

## Boundaries & Constraints

**Always:**
- El nuevo componente vive solo dentro del tablero automático (`analysis-dashboard`); el notebook libre y el módulo guiado (que reutilizan `cell-result.component`) deben seguir mostrando `chart_svg` exactamente igual que hoy — criterio de no-regresión (UX-DR5).
- La gráfica es de doble eje: barras (valor, eje izquierdo) + línea de `% acumulado` (eje derecho, 0-100), replicando la forma visual que el SVG ya produce hoy (`table_builder.py::_pareto_chart_lines`) — no es una simplificación a solo-barras.
- Instalar `chart.js` con `yarn` (el proyecto usa yarn, no npm — ver `README.md`/`COMO_PROBAR.md`).

**Never:**
- No tocar `backend/app/notebook/` — el backend ya expone todo lo necesario.
- No tocar `no-code-chart.component` ni su endpoint `/generate-chart` (flujo manual, historia separada si algún día se decide migrar).
- No implementar todavía tooltip enriquecido, animación de entrada ni la anotación del 80% — eso es 10.2, 10.3 y 10.4. Chart.js trae tooltip por defecto de fábrica; es aceptable que se vea genérico en esta historia.
- No tocar el theming/colores por design token — eso es 10.5; usar los colores por defecto de Chart.js en esta historia.

</frozen-after-approval>

## Code Map

- `frontend/package.json` -- agregar dependencia `chart.js` (última versión estable 4.x).
- `frontend/src/app/shared/chart-canvas/` (nuevo) -- `chart-canvas.component.ts/.html/.scss`. Input: `records: Record<string, unknown>[]`, `categoryKey: string` (= `bloque.dimension`), `valueKey: string` (= `bloque.metrica`). Renderiza `<canvas>` + Chart.js tipo `bar` con dataset secundario tipo `line` en `yAxisID` distinto para `% acumulado`.
- `frontend/src/app/shared/shared-module.ts` -- declarar y exportar `ChartCanvasComponent`.
- `frontend/src/app/shared/cell-result/cell-result.component.ts` (línea ~36, getter `safeChartSvg`) y `.html` (líneas ~39-52/62-64) -- agregar `@Input() hideChart = false`; cuando es `true`, no renderizar el bloque de `chart_svg`. Default `false` preserva todo uso existente (notebook libre, guiado) sin cambios.
- `frontend/src/app/shared/analysis-dashboard/analysis-dashboard.component.html` (línea ~44) -- pasar `[hideChart]="true"` a `<app-cell-result>` y agregar `<app-chart-canvas [records]="bloque.resultado.result_records" [categoryKey]="bloque.dimension" [valueKey]="bloque.metrica">` junto a él, solo cuando `bloque.resultado.result_records` no es null/vacío.
- `frontend/src/app/models/api.models.ts` -- ningún cambio de tipos necesario; `result_records?: Record<string, unknown>[] | null` ya existe en `CellResult`.

**Dato de formato a manejar en `chart-canvas.component.ts`:** cuando la columna de valor "parece dinero" (backend: `_looks_like_money()`), cada valor en `result_records[valueKey]` llega **ya formateado como string** `"$ 12.345"` (prefijo `"$ "` + miles con `.`, sin decimales — formato fijo de `table_builder.py::_money_format_expr`), no como número. El componente debe detectar el string y parsearlo (`quitar "$ " y todos los "."`, luego `Number(...)`) antes de graficar. Si el valor ya es number, usarlo directo.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/package.json` -- agregar `chart.js` -- necesario para renderizar
- [x] `frontend/src/app/shared/chart-canvas/chart-canvas.component.ts/.html/.scss` -- nuevo componente de gráfica Pareto interactiva -- núcleo de la historia
- [x] `frontend/src/app/shared/shared-module.ts` -- registrar el componente nuevo
- [x] `frontend/src/app/shared/cell-result/cell-result.component.ts/.html` -- agregar `hideChart` input -- permite ocultar el SVG solo desde el tablero automático
- [x] `frontend/src/app/shared/analysis-dashboard/analysis-dashboard.component.html` -- usar `hideChart` + montar `app-chart-canvas` por bloque -- conecta todo

**Acceptance Criteria:**
- Given un bloque del tablero automático con `result_records` no vacío, when se renderiza `analysis-dashboard`, then aparece una gráfica Chart.js (barras + línea) en vez del SVG, y el SVG no se muestra duplicado.
- Given una columna de valor que "parece dinero" (ej. `neto`, `venta`), when el componente arma el dataset, then las barras usan el valor numérico real (parseado desde el string `"$ ..."`), no `NaN` ni el string crudo.
- Given el notebook libre o una lección del módulo guiado ejecutando cualquier celda con gráfica, when se renderiza `cell-result`, then el comportamiento es idéntico al actual (SVG inline, sin `hideChart`).
- Given un bloque cuyo `resultado.error` no es null, when se renderiza, then no se intenta montar `app-chart-canvas` (ya lo maneja `*ngIf`/`@if` sobre `result_records`).

## Implementation Notes

- `chart.js@4.5.1` instalado con `yarn add chart.js` (no `npm`).
- `chart-canvas.component.ts` registra `Chart.register(...registerables)` (set completo, no tree-shaking manual) y crea un chart tipo `bar` con un segundo dataset tipo `line` (`% acumulado`) en `yAxisID: 'y1'` (0-100, `drawOnChartArea: false` para no duplicar la grilla). `ngOnChanges` actualiza `chart.data`/`chart.options` y llama `chart.update()` en vez de destruir/recrear; `ngOnDestroy` llama `chart.destroy()`.
- Parseo de "parece dinero": ahora vive en `frontend/src/app/shared/money-format.ts` como `parseMoneyValue(raw: string): number` (quita `'$'` y todos los `.`, hace `Number(...)`) — `chart-canvas.component.ts`'s `toNumber()` la importa y la usa; si el valor ya es `number` lo usa directo. Centralizado tras revisión (hallazgo #5 del Review Triage Log) para que quede un único lugar con la heurística de formato de dinero, en sync con el backend.
- Fix de revisión (#2): `toNumber()`/`parseMoneyValue()` devuelven `NaN` (no `0`) cuando el string no parsea a un número finito, y `toNumber()` también devuelve `NaN` para cualquier valor que no sea `number`/`string` — Chart.js renderiza un hueco en ese punto en vez de una barra de cero engañosa.
- Fix de revisión (#7): `<canvas>` ahora tiene `role="img"` y `[attr.aria-label]` calculado (getter `chartAriaLabel`) con la métrica, la dimensión y el conteo de categorías — reemplaza el `<title>` nativo por barra que tenía el SVG con un resumen accesible (no por-barra, pero ya no silencioso).
- Fix de revisión (#13, #14): se agregaron `frontend/src/app/shared/chart-canvas/chart-canvas.component.spec.ts` (mapeo `records` → dataset de Chart.js, incluyendo un valor formateado como dinero, el caso `NaN` para valor no parseable, y el `aria-label`) y `frontend/src/app/shared/analysis-dashboard/analysis-dashboard.component.spec.ts` (con `result_records` no vacío, verifica que el bloque `.chart`/`svg` de `cell-result` esté ausente y que `app-chart-canvas canvas` esté presente). Ambos verificados en verde con `ng test --include=.../chart-canvas/**/*.spec.ts --include=.../analysis-dashboard/**/*.spec.ts` (4/4 SUCCESS).
- `hideChart` se implementó ocultando el bloque en el getter `safeChartSvg` (retorna `null` cuando `hideChart` es `true`) en vez de tocar `cell-result.component.html` — el `@if (safeChartSvg)` existente ya no renderiza nada, y el lightbox (`expanded === 'chart' && safeChartSvg`) queda igualmente inerte. Cumple el AC sin duplicar la condición en la plantilla; el archivo `.html` de `cell-result` quedó sin cambios.
- `bloque.resultado.result_records!` en la plantilla usa non-null assertion dentro del `@if` que ya comprobó `result_records?.length` (truthy) — compila limpio bajo `strictTemplates`.

## Spec Change Log

**2026-09-23 — Hotfix post-ship, encontrado en QA manual (no en las 24 revisiones automatizadas de las Stories 10.1-11.3):**

- **Qué se encontró:** al probar visualmente el tablero automático con archivos Excel reales (no sintéticos) subidos por el usuario, la pestaña del navegador se congelaba de forma indefinida (loop consumiendo un núcleo de CPU al 100%) justo al renderizar el tablero (Paso 3). Reproducido de forma determinística con 2 archivos reales distintos, tanto en pruebas automatizadas propias como en pruebas manuales independientes del usuario en una ventana de Chrome nueva.
- **Investigación:** se probó primero el commit baseline (anterior a toda la Épica 10) con el mismo archivo — el baseline renderizó el tablero completo (SVG, 6 bloques) sin ningún problema, descartando que fuera un bug preexistente. Luego se aisló Chart.js: un harness HTML standalone (mismo Chart.js 4.5.1 + chartjs-plugin-annotation 3.1.0, misma configuración exacta de `chart-canvas.component.ts`, mismos datos reales exportados del backend) renderizó los 6 gráficos instantáneamente sin Angular — descartando a Chart.js y a los datos como causa.
- **Causa raíz confirmada:** Chart.js con `responsive: true` usa internamente un `ResizeObserver`, y su animación usa `requestAnimationFrame` — Zone.js parchea ambos, así que cada tick de resize/animación reentraba a la zona de Angular y disparaba un ciclo completo de detección de cambios. Dentro del `CSS Grid` del tablero (columnas `auto-fit`, canvas a `width: 100%`), un cambio de layout de un solo píxel en cualquiera de los 6 gráficos podía retroalimentarse: resize → detección de cambios de Angular → resize → ... — un loop autosostenido que nunca se detenía por sí solo.
- **Fix aplicado:** `chart-canvas.component.ts` ahora inyecta `NgZone` y ejecuta toda la creación/actualización de Chart.js dentro de `ngZone.runOutsideAngular(...)`, para que los listeners internos de Chart.js (ResizeObserver, rAF) nunca vuelvan a entrar a la zona de Angular. Verificado en vivo: el mismo archivo que colgaba la pestaña ahora renderiza el tablero interactivo completo, con tooltips, animación y línea del 80% funcionando, sin ningún freeze.
- **Test de regresión agregado:** `chart-canvas.component.spec.ts` verifica con un spy sobre `NgZone.runOutsideAngular` que toda llamada a `render()` pasa por ahí — falla si un cambio futuro mueve la creación/actualización de Chart.js de vuelta dentro de la zona de Angular.
- **KEEP:** todo el resto de `chart-canvas.component.ts` (tooltip, animación, anotación del 80%, colores por token) se mantiene exactamente igual — el fix es puramente el envoltorio `runOutsideAngular` alrededor de la lógica ya existente, cero cambios de comportamiento visual.

## Review Triage Log

| # | Fuente | Hallazgo | Veredicto | Evidencia |
|---|--------|----------|-----------|-----------|
| 1 | blind-hunter | `'% acumulado'` hardcodeado en vez de `@Input` | false | Único caller actual (`analysis-dashboard`) siempre produce esa clave literal (`table_builder.py::build_summary_code`, columna fija en el DataFrame generado) — no hay mismatch alcanzable hoy. |
| 2 | blind-hunter | `toNumber()` degrada valores no parseables a `0` sin señal | medium | Real: un valor inesperado se vería como categoría en cero sin indicio de error — misleading para una gráfica de negocio. Fix trivial (patch). |
| 3 | blind-hunter | Guard del dashboard no valida `dimension`/`metrica` no vacíos → posible regresión neta si el chart no-opera | false | `bloque.dimension`/`bloque.metrica` siempre vienen poblados con nombres de columna reales desde `analysis_catalog.py::build_catalog()` — estado inalcanzable con el único caller actual. |
| 4 | blind-hunter | Sin tests unitarios para `chart-canvas.component.ts` | medium (carried) | Cubierto de forma concreta y verificada por los hallazgos 13 y 14 de verification-gap; no se abre como entrada separada. |
| 5 | blind-hunter | Parseo de dinero debería vivir en `money-format.ts` en vez de duplicarse | low | Verificado: `money-format.ts` hoy solo exporta `looksLikeMoney(nombre)` (clasifica NOMBRES de columna), no tiene parseo de valores — no hay duplicación literal todavía, pero centralizar el parseo "$ "+"." ahí es la mejora de consistencia obvia. Fix trivial (patch). |
| 6 | blind-hunter | Nombre/selector genérico sin opt-out de forma (Pareto fija) para reutilización futura | low | Rechazado: preocupación especulativa sobre mal uso futuro; el único caller actual y los Boundaries de la spec exigen exactamente esta forma (doble eje Pareto). Poco probable en uso cotidiano. |
| 7 | blind-hunter | `<canvas>` sin `aria-label`, hueco de accesibilidad | low | Real: regresión menor frente al `<title>` nativo por barra que tenía el SVG. Bajo impacto práctico (herramienta interna, 2-3 usuarios) pero fix trivial (patch). |
| 8 | blind-hunter | Comentario de invariante de `hideChart` no aplicado por lint/runtime | low | Rechazado: sin daño concreto nombrado (ningún caller identificado que vaya a divergir); aplicarlo de verdad (lint/runtime) sería más que una corrección trivial. |
| 9 | blind-hunter | Sin estado vacío/loading — `records=[]` renderiza canvas en blanco | false | El propio guard `@if` de `analysis-dashboard.component.html` (`result_records?.length`) impide que `chart-canvas` se monte alguna vez con `records` vacío en la integración actual. |
| 10 | edge-case-hunter | `render()` sin guard para `records.length === 0` | false | Mismo reclamo que la fila 9, misma refutación. |
| 11 | edge-case-hunter | `categoryKey`/`valueKey` podrían no coincidir con las claves reales del record | false | Verificado en `table_builder.py`/`execution.py`: para el único caller (agrupación de una sola columna), la clave de categoría y de valor del record siempre son exactamente `bloque.dimension`/`bloque.metrica`. |
| 12 | edge-case-hunter | El record podría no traer la clave hardcodeada `'% acumulado'` | false | Mismo reclamo que la fila 1, misma refutación. |
| 13 | verification-gap | Sin test que proteja la supresión del SVG duplicado (`hideChart`) | medium | Pre-verificado por la capa (evidencia: cero specs de `AnalysisDashboardComponent` en el repo). Riesgo real: un futuro edit del template podría reintroducir el doble-render sin que nada lo detecte. Disposición filed: patch. |
| 14 | verification-gap | Sin test del mapeo `records` → datos de Chart.js (`toNumber`, serie acumulada) | medium | Pre-verificado por la capa (evidencia: cero specs de `ChartCanvasComponent`). Riesgo real: un cambio de formato rompería el parseo o la clave `'% acumulado'` sin que ningún test lo detecte. Disposición filed: patch. |

**Sobreviven a patch:** #2, #5, #7, #13, #14 (ninguna comparte causa raíz con otra — 5 entradas independientes). Sin `intent_gap` ni `bad_spec` — la implementación sigue la spec fielmente; todo lo que sobrevive es robustez/cobertura adicional, no una desviación.

## Verification

**Commands:**
- `cd frontend && yarn build` -- expected: compila sin errores de TypeScript.
- `cd frontend && yarn test --watch=false` -- expected: specs existentes de `cell-result` y `analysis-dashboard` (si existen) siguen en verde.

**Manual checks (if no CLI):**
- Levantar la app local (`COMO_PROBAR.md`), subir un Excel real al módulo sin código, confirmar columnas, y verificar visualmente que el tablero automático muestra gráficas Chart.js (canvas, no imagen) para cada bloque, y que el módulo guiado / notebook libre siguen mostrando SVG sin cambios.

**Results:**
- `yarn build`: compiló sin errores de TypeScript/plantillas (solo un warning preexistente de presupuesto SCSS en `convatec-home.component.scss`, no relacionado con esta historia).
- `yarn test --watch=false --browsers=ChromeHeadless`: no existen specs de `cell-result`/`analysis-dashboard` en el repo (solo `app.spec.ts`). `app.spec.ts` falla con `NG0304: 'app-tour-overlay' is not a known element` — confirmado como **preexistente en baseline** (reproducido idéntico con `git stash` sobre `master`/`8cf61eb`, antes de cualquier cambio de esta historia). No hay regresión atribuible a esta historia.
- No se realizó la verificación manual con Excel real en navegador (fuera del alcance de este agente) — queda pendiente para el revisor humano.
