---
status: 'analysis'
completedAt: '2026-09-23'
inputDocuments: ['epics-modulo-nocode-sico-pandas-lab-2026-07-18.md', 'analisis-interactividad-ux-guiado-nocode-sico-pandas-lab-2026-09-21.md']
relatedTo: 'Mesa redonda (bmad-party-mode) 2026-09-23, a pedido del dueño del producto: "veo que no es un dashboard [de verdad] y sería bueno tener un dashboard completo de todo el análisis sin tener que dar más clic sino un solo clic para todo." Continuación directa de la sesión que entregó las Épicas 10-11 (gráficos interactivos + progreso del guiado), ya en producción.'
---

# sico-pandas-lab — Análisis en un clic (módulo sin código)

Análisis discutido en mesa redonda (analista, PM, UX, arquitecto, dev). Objetivo:
reducir la fricción del flujo "sin código" (subir → confirmar limpieza → confirmar
clasificación → generar análisis) a la mínima expresión, sin perder la corrección
humana que existe hoy porque la clasificación automática de columnas puede
equivocarse.

## El hallazgo que reordena el pedido

El pedido del dueño del producto ("un solo clic para todo") sonaba como que había
que rediseñar 3 pasos. Al inspeccionar el código, resultó que **uno de los tres ya
está resuelto**:

- **Paso de limpieza del Excel (Épica 4):** cuando el veredicto del perfilador es
  `usable` (encabezado limpio, sin ambigüedad), `data-source-panel.component.ts`
  (línea 116) **ya salta la confirmación** — emite `loaded` de inmediato, sin clic.
  Solo pide confirmación cuando el veredicto es `usable_con_limpieza` (caso real:
  encabezado mal detectado, columnas basura intercaladas) — ahí el clic es
  necesario porque el sistema literalmente no sabe si acertó.
- **Paso de clasificación de columnas:** este SIEMPRE pide confirmación hoy, con
  o sin asistente de IA disponible, porque no hay ninguna señal de confianza por
  columna en el backend (`semantic_classifier.py::classify_columns()` devuelve un
  booleano `usedAssistant` global, nunca una confianza por columna). Este es el
  único punto de fricción real que queda por resolver.

**Decisión de UX (con desacuerdo real en la mesa, resuelto):** la opción rechazada
fue "auto-confirmar siempre y esconder el paso de clasificación" — sin una señal
de confianza por columna, eso es apostar a que el fallback de reglas simples nunca
se equivoque, y ya se documentó un caso real (Épica 10, mismo archivo de pruebas)
donde el encabezado mal detectado produce columnas sin nombre (`col_9`). La opción
elegida es invertir el orden: generar el análisis automáticamente en cuanto la
clasificación sugerida está lista (ya se calcula sola, sin clic, vía
`ColumnClassificationComponent.ngOnChanges` → `fetchSuggestion()`), y mover la
corrección humana de "antes del resultado" a "encima del resultado" — un panel
para reabrir y ajustar la clasificación sin perder el tablero ya visible.

**Caso de referencia:** el mismo archivo real ya usado para las Épicas 4 y 10
(encabezado mal detectado, columnas `col_N`) sigue siendo la prueba de fuego: si
la clasificación automática le pone rol equivocado a alguna columna, el usuario
debe poder corregirlo sin tener que volver a subir el archivo ni perder lo que ya
vio.

---

## Épica 12 — Análisis en un clic

**Objetivo:** que el tablero automático aparezca apenas se sube un Excel con
veredicto `usable` (cero clics intermedios) o apenas se confirma una limpieza
necesaria (un clic, no tres), sin eliminar la posibilidad de corregir la
clasificación de columnas si el sistema se equivocó.

**Decisión de arquitectura (no negociable):** cero cambios de backend. Tanto
`semantic_classifier.py::classify_columns()` como
`analysis_catalog.py::build_catalog()` ya soportan exactamente este flujo tal
como están — la clasificación ya se calcula sola al llegar el perfil, y
regenerar el catálogo completo a partir de una clasificación corregida es
literalmente la misma llamada que ya existe (`autoAnalysis(classifications)`).
Todo el trabajo es de `frontend/src/app/no-code/no-code-home/` y
`frontend/src/app/shared/column-classification/`.

**Decisión de alcance (explícita, no un pendiente):** corregir una columna
después de ver el tablero **regenera el catálogo completo**, no parchea un solo
bloque. `build_catalog()` no tiene ni necesita hoy un modo incremental — el
volumen de datos (2-3 usuarios, archivos típicos de pocas columnas) no lo
justifica.

**Decisión de alcance (fuera de este corte):** no se toca `analysis-dashboard`
ni `chart-canvas` (Épica 10, con el fix de Zone.js ya en producción — no
revertir ni evadir ese fix). No se agrega ninguna señal de confianza por
columna al backend — sigue siendo "confía en la sugerencia, corrige si hace
falta", no "el sistema decide solo cuándo confiar en sí mismo".

**Alcance técnico:**
- `frontend/src/app/no-code/no-code-home/no-code-home.component.ts`: en cuanto
  `column-classification` emite la clasificación sugerida (hoy solo se emite al
  hacer clic en "Confirmar y generar análisis"), disparar `autoAnalysis()`
  automáticamente sin esperar ese clic.
- `frontend/src/app/shared/column-classification/column-classification.component.ts`:
  emitir el evento `confirmed` automáticamente apenas `fetchSuggestion()`
  resuelve, en vez de esperar al método `confirm()` ligado a un botón. El botón
  y los selectores de rol por columna se conservan, pero pasan a ser un panel
  de corrección post-resultado, no un formulario bloqueante.
- Cambio de copy (Sally): de "Confirma qué es cada columna" (bloqueante) a un
  mensaje informativo tipo "Así interpretamos tu archivo" con salida clara a
  corregir, coherente con que el tablero ya está visible debajo.
- Corregir una columna vuelve a llamar `autoAnalysis()` con la clasificación
  ajustada, reemplazando el tablero anterior — mismo mecanismo que ya usa el
  flujo actual, solo que ahora también se puede disparar después de ya haber
  visto un resultado.

**Criterios de aceptación clave:**
- Con un Excel cuyo veredicto de limpieza es `usable`, el tablero aparece sin
  ningún clic intermedio después de subir el archivo.
- Con un Excel que necesita limpieza (`usable_con_limpieza`), el tablero
  aparece con un solo clic (confirmar limpieza) — la clasificación de columnas
  ya no pide un segundo clic aparte.
- Si la clasificación automática le puso un rol equivocado a una columna, el
  usuario puede corregirlo desde un panel visible junto al tablero, sin volver
  a subir el archivo, y el tablero se regenera con la corrección.
- El notebook libre y el módulo guiado no cambian — este flujo es exclusivo de
  `no-code-home`.

## Relación con trabajo ya planeado

No reemplaza ni bloquea las Épicas 10 y 11 (ya en producción) ni la Épica 9
(KPIs ejecutivos, backlog). Se numera 12 para no chocar con la numeración
existente. Depende de que las Épicas 4-8 (perfilado, clasificación, catálogo
automático) sigan funcionando tal como están — no las modifica, solo cambia
cuándo se disparan desde el frontend.
