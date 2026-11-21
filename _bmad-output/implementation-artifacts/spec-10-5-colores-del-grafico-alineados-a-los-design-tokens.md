---
title: 'Story 10.5: Colores del gráfico alineados a los design tokens'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
baseline_commit: '8b18250'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `chart-canvas.component.ts` usa colores por defecto de Chart.js (barra) y placeholders fijos (`REFERENCE_LINE_COLOR = '#888888'` para la línea del 80%, con un TODO explícito de contraste insuficiente desde la Story 10.4) — ninguno viene de los design tokens compartidos de `styles.scss` (`--brand`, `--warn`, `--ink-muted`, etc.), a diferencia del resto de la app.

**Approach:** Leer los tokens de color existentes en runtime vía `getComputedStyle(document.documentElement).getPropertyValue('--token')` (con fallback al valor hex actual si el token no existe, por robustez) y aplicarlos: `--brand` para las barras, `--warn` para la línea de `% acumulado` (evita reusar `--bad`, que tiene carga semántica de "error", para una línea que no representa un problema), y `--ink-muted` para la línea/etiqueta de referencia del 80% — que de paso resuelve el TODO de contraste de la Story 10.4 (blanco sobre `--ink-muted` da ~5.5:1, sobre el mínimo AA de 4.5:1). No se declara ninguna paleta nueva ni se elige un color sin precedente en la app.

</frozen-after-approval>

## Implementation Notes

- `chart-canvas.component.ts`: nueva función `designToken(name, fallback)` que lee `getComputedStyle(document.documentElement).getPropertyValue(name)`, con fallback al hex actual si el token no resuelve (ej. entorno de test sin stylesheet). Reemplaza `REFERENCE_LINE_COLOR` (constante fija de la Story 10.4).
- Barras: `--brand`. Línea `% acumulado`: `--warn` (deliberadamente no `--bad`, que en el resto de la app significa "error"). Línea/etiqueta del 80%: `--ink-muted` — de paso resuelve el TODO de contraste dejado por la Story 10.4 (blanco sobre `--ink-muted` ≈5.5:1, sobre el mínimo AA).
- Test nuevo: sobreescribe los tokens vía `document.documentElement.style.setProperty` y verifica que el chart usa esos valores exactos, no un hex hardcodeado.
- `yarn build` limpio; 11/11 tests en verde (12/12 tras el parcheo).
- Revisión (blind-hunter): 8 hallazgos, 7 sobreviven, parchados en el mismo pase:
  - Cifra de contraste corregida (~6.1:1 real, no ~5.5:1 como se escribió inicialmente).
  - `--warn` reemplazado por `--brand-dark` para la línea acumulada — `--warn` ya se usa en la app para avisos/precaución (`convatec-maestros`, `cell-result`, etc.), semánticamente incorrecto para una línea normal.
  - Extendidos a tokens: texto de la leyenda, fondo/texto del tooltip, y color de ticks/grid de los tres ejes (antes quedaban en los defaults de Chart.js, contradiciendo el comentario de clase que decía "cada color").
  - Comentario agregado señalando que los valores de fallback deben mantenerse sincronizados a mano con `styles.scss`.
  - Colores memorizados una sola vez por instancia (`resolveColors()`) en vez de releer `getComputedStyle` en cada `render()`/`update()` — la app no tiene cambio de tema en runtime, así que el valor es efectivamente fijo por carga de página.
  - Test nuevo: `line80.label.backgroundColor` (antes solo se verificaba `borderColor`, pese a venir de la misma variable).
  - Test nuevo: camino de fallback cuando un token resuelve a string vacío (el caso real que dispara el fallback en un navegador; la rama `typeof document === 'undefined'` es inalcanzable en Karma).
  - Rechazado: tokenizar `borderColor` de la barra — Chart.js no dibuja borde visible con `borderWidth: 0` (el default), así que no hay nada que tokenizar ahí.

## Review Triage Log

| # | Hallazgo | Veredicto | Evidencia |
|---|----------|-----------|-----------|
| 1 | Cifra de contraste documentada (~5.5:1) incorrecta | low | Real, recalculado ≈6.13:1. Patch (corrección de comentario/spec). |
| 2 | Claim de "cada color" sobrestimado — leyenda/tooltip/ejes seguían en default | medium | Real y visible; se extendió la tokenización en vez de solo corregir el texto. Patch. |
| 3 | `--warn` para la línea acumulada choca con su uso de "precaución" en el resto de la app | medium | Real, verificado (uso en `convatec-maestros`, `cell-result`, etc.). Patch (`--brand-dark`). |
| 4 | Fallbacks hex sin mecanismo que los mantenga sincronizados con `styles.scss` | low | Real pero de bajo impacto práctico. Patch (comentario). |
| 5 | Sin test del camino de fallback de `designToken()` | low | Real gap de cobertura. Patch. |
| 6 | `getComputedStyle` releído en cada render/update sin necesidad (app sin cambio de tema en runtime) | low | Real, optimización barata. Patch (memorizado por instancia). |
| 7 | Barra solo tokeniza `backgroundColor`, no `borderColor` | false | Chart.js usa `borderWidth: 0` por defecto — sin borde visible, nada que tokenizar. |
| 8 | Test no verifica `line80.label.backgroundColor`, solo `borderColor` | low | Real gap de cobertura, misma variable en ambos. Patch. |

