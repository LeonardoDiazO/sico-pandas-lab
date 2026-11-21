---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - 'analisis-un-clic-dashboard-nocode-sico-pandas-lab-2026-09-23.md'
  - 'epics-modulo-nocode-sico-pandas-lab-2026-07-18.md'
  - 'epics.md'
  - 'sprint-status-sico-pandas-lab.yaml'
---

# sico-pandas-lab - Epic Breakdown (Épica 12: Análisis en un clic)

Este documento cubre exclusivamente la **Épica 12**, nueva, salida de la mesa
redonda del 2026-09-23 sobre reducir la fricción del flujo del módulo sin
código. Las Épicas 1-11 ya existen y **no se tocan aquí**.

**Nota de alcance:** esta épica no requiere ningún FR nuevo del PRD original —
opera enteramente sobre capacidades ya existentes de las Épicas 4-8 (perfilado,
clasificación semántica, catálogo automático), cambiando únicamente CUÁNDO se
disparan desde el frontend, no QUÉ hacen.

## Requirements Inventory

### Functional Requirements

_(existentes, sin cambios — contexto para esta épica)_

FR-NC3 (Épica 4, `excel_profiler.py`): el sistema emite un veredicto de 3
estados al subir un Excel — `usable`, `usable_con_limpieza`, `no_usable`.
FR-NC4 (Épica 4, `data-source-panel.component.ts`): cuando el veredicto es
`usable`, el DataFrame se vincula sin pedir confirmación humana.
FR-NC5 (Épica 5, `semantic_classifier.py`): el sistema sugiere un rol
(dimensión/métrica/fecha/identificador/descartar) para cada columna en cuanto
se conoce el perfil, con o sin asistente de IA disponible.
FR-NC6 (Épica 8, `analysis_catalog.py`): el sistema genera un catálogo de
bloques de análisis (tabla + gráfica Pareto) a partir de una clasificación de
columnas confirmada.

### NonFunctional Requirements

NFR1 (Reliability): un error al generar el análisis automático debe mostrarse
con un mensaje claro, sin romper la sesión — ya cubierto por
`onClassificationConfirmed()`'s manejo de error existente, sin cambios.
NFR2 (Usability): el flujo debe minimizar clics sin eliminar la posibilidad de
corregir una clasificación equivocada — esta es la NFR que motiva la épica.

### Additional Requirements

- Cero cambios de backend: `semantic_classifier.py::classify_columns()` y
  `analysis_catalog.py::build_catalog()` ya soportan el flujo propuesto tal
  como están.
- No modificar `analysis-dashboard.component`/`chart-canvas.component` (Épica
  10) — incluye el fix de Zone.js (`NgZone.runOutsideAngular`) ya en
  producción, que no debe revertirse ni evadirse.
- Corregir una clasificación después de ver el tablero regenera el catálogo
  completo (todo-o-nada) — decisión explícita, no un pendiente técnico.

### UX Design Requirements

_(del documento de análisis de la mesa redonda, mismo tratamiento que en el
ciclo anterior — no existe un DESIGN.md/EXPERIENCE.md formal en este proyecto)_

UX-DR11: Con un Excel de veredicto `usable`, el tablero aparece sin ningún
clic intermedio después de subir el archivo.
UX-DR12: Con un Excel de veredicto `usable_con_limpieza`, el tablero aparece
con un solo clic (confirmar limpieza) — la clasificación de columnas ya no
pide un segundo clic aparte.
UX-DR13: La clasificación de columnas se muestra como panel de corrección
visible junto al tablero (no como formulario bloqueante previo), con copy
informativo ("Así interpretamos tu archivo") en vez de una instrucción de
confirmación obligatoria.
UX-DR14: Corregir el rol de una columna desde ese panel regenera el tablero
completo con la clasificación ajustada.

### FR Coverage Map

FR-NC3, FR-NC4: Epic 12 - contexto ya implementado, sin cambios; la épica se apoya en este comportamiento existente.
FR-NC5, FR-NC6: Epic 12 - se reutilizan tal cual, solo cambia cuándo se invocan desde el frontend.
UX-DR11: Epic 12 - cero clics cuando el veredicto es usable.
UX-DR12: Epic 12 - un solo clic cuando hace falta limpieza.
UX-DR13: Epic 12 - panel de corrección post-resultado, copy informativo.
UX-DR14: Epic 12 - regeneración completa del catálogo al corregir.

## Epic List

### Epic 12: Análisis en un clic

Quien sube un Excel al módulo sin código ve el tablero automático de
inmediato — sin clics intermedios si el archivo ya está limpio, con uno solo
si necesita limpieza — y puede corregir la clasificación de columnas desde un
panel junto al tablero si el sistema se equivocó, sin volver a subir el
archivo.

**FRs covered:** FR-NC3, FR-NC4, FR-NC5, FR-NC6 (reutilizadas), UX-DR11, UX-DR12, UX-DR13, UX-DR14

**Nota:** sin dependencias con las Épicas 9, 10 ni 11. Depende de que las
Épicas 4-8 sigan funcionando tal como están (no las modifica).

### Story 12.1: Ver el tablero automático sin esperar un clic de confirmación

Como usuario que sube un Excel al módulo sin código,
quiero que el tablero automático se genere en cuanto la clasificación de columnas está lista,
para no tener que hacer clic en "confirmar" antes de ver mi análisis.

**Acceptance Criteria:**

**Given** que subí un Excel con veredicto de limpieza `usable` (o ya confirmé la limpieza de uno `usable_con_limpieza`)
**When** la clasificación de columnas sugerida termina de calcularse
**Then** el tablero automático se genera y se muestra sin que yo tenga que hacer clic en ningún botón de confirmación
**And** si el veredicto era `usable`, no hay ningún clic intermedio entre subir el archivo y ver el tablero
**And** si el veredicto era `usable_con_limpieza`, el único clic necesario es el de confirmar la limpieza

### Story 12.2: Corregir la clasificación de una columna después de ver el tablero

Como usuario que ya ve el tablero automático,
quiero poder corregir el rol de una columna si el sistema lo clasificó mal,
para arreglar mi análisis sin tener que volver a subir el archivo.

**Acceptance Criteria:**

**Given** que el tablero automático ya está visible
**When** abro el panel de corrección de columnas
**Then** veo la clasificación sugerida para cada columna, editable, con el mismo mecanismo de selección que existe hoy
**And** al cambiar el rol de una columna y confirmar, el tablero se regenera completo con la nueva clasificación
**And** el archivo no se vuelve a subir ni se pierde el estado de la sesión

### Story 12.3: Mensaje informativo en vez de formulario bloqueante

Como usuario que llega al panel de clasificación de columnas,
quiero que el texto me diga cómo se interpretó mi archivo, no que me exija confirmar antes de continuar,
para entender que ya tengo un resultado y que corregir es opcional, no un paso obligatorio.

**Acceptance Criteria:**

**Given** que el tablero automático ya se generó a partir de la clasificación sugerida
**When** veo el panel de clasificación de columnas junto al tablero
**Then** el texto es informativo (p. ej. "Así interpretamos tu archivo"), no una instrucción de confirmación obligatoria
**And** el llamado a la acción para corregir es claramente opcional, distinto en tono del botón de confirmación que existía antes
