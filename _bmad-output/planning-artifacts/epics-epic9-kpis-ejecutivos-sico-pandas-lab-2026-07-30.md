---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete'
completedAt: '2026-07-30'
inputDocuments: ['prd-sico-pandas-lab-2026-07-12.md', 'architecture-sico-pandas-lab-2026-07-12.md', 'epics-modulo-nocode-sico-pandas-lab-2026-07-18.md', 'sprint-change-proposal-sico-pandas-lab-2026-07-28.md']
continuesFrom: 'sprint-change-proposal-sico-pandas-lab-2026-07-28.md (Epic 8, ya done) y epics-modulo-nocode-sico-pandas-lab-2026-07-18.md (Epic 4-6)'
---

# sico-pandas-lab (Epic 9: Resumen ejecutivo con múltiples KPIs) - Epic Breakdown

This document provides the epic and story breakdown for Epic 9 of sico-pandas-lab,
decomposiendo el alcance acordado en la sesión de party-mode del 2026-07-30 (evidencia
real contra el archivo "detallado comfenalco (S01-2077).xlsx") en historias implementables.
No existe documento de UX formal para este proyecto (mismo caso que Epic 4-6 y 8); los
UX-DR de abajo salen de esa misma sesión de diseño.

## Requirements Inventory

### Functional Requirements

**Nota de alcance:** FR1-FR21 (Épicas 1-3), FR22-FR29 (Épicas 4-6) y FR30-FR32 (Epic 8,
ya `done`) no se repiten aquí — ver los documentos anteriores. Este documento solo
cubre los FR nuevos de Epic 9.

FR33: Un usuario puede fijar (pin) hasta 4 resúmenes agrupados (el mecanismo de Story 8.2/8.3) simultáneamente en pantalla, cada uno con su propia columna(s) de agrupación y columna de valor, sin que generar un resumen nuevo reemplace los ya fijados.
FR34: Un usuario puede quitar individualmente cualquier resumen fijado, sin afectar los demás.
FR35: Cuando la columna de valor elegida para un resumen agrupado contiene tanto filas positivas como negativas, el sistema calcula y muestra por separado, para cada grupo, el total positivo ("venta"), el total negativo ("pérdida/devolución") y el neto.
FR36: Cuando aplica el desglose de FR35, el sistema muestra una frase en español simple explicando la relación entre venta, pérdida/devolución y neto (mismo patrón que `table_explanation.py`).

### NonFunctional Requirements

**Nota de alcance:** NFR1-NFR9 (Épicas 1-3), NFR10-NFR12 (Épicas 4-6) no se repiten aquí.
Epic 9 no introduce NFRs nuevos — reutiliza el mismo principio de seguridad de conjunto
cerrado (NFR10) ya establecido, extendido de forma natural a esta épica.

### Additional Requirements

- Reutiliza el endpoint `POST /summary-table` ya existente (Story 8.2) — se llama una vez por resumen fijado (FR33), sin ruta nueva.
- El desglose de signo mixto (FR35) se calcula en el mismo `groupby` de `table_builder.py::build_summary_code`, separando filas por signo antes de sumar (`df[df[col] > 0]` / `df[df[col] < 0]`) — sin mecanismo de ejecución nuevo, mismo `WorkerManager.execute()` de siempre.
- Explícitamente fuera de alcance (decidido en la sesión de diseño): detectar automáticamente qué columna "es" venta o cuál "es" gasto/pérdida — la columna de valor la sigue eligiendo el usuario manualmente, igual que en Epic 8.
- El tope de 4 resúmenes fijados (FR33) es una decisión de UX deliberada para evitar la misma sobrecarga visual de la que se quejó el usuario originalmente (sesión de party-mode, Mary: "sin límite, esto se vuelve la misma sopa visual").

### UX Design Requirements

UX-DR6: Los resúmenes fijados (FR33) se muestran simultáneamente en pantalla (no uno reemplazando al otro), cada uno con un control visible para quitarlo individualmente (FR34).
UX-DR7: Cuando el desglose de signo mixto aplica (FR35), se muestran los 3 valores (venta, pérdida, neto) visualmente diferenciados entre sí — no como una sola cifra neta — acompañados de la frase explicativa (FR36). Cuando la columna no trae signo mixto, no se muestra ninguna categoría de "pérdida" falsa o en cero.

### FR Coverage Map

```
FR33: Epic 9 - Fijar hasta 4 resúmenes agrupados simultáneamente
FR34: Epic 9 - Quitar un resumen fijado individualmente
FR35: Epic 9 - Desglose venta/pérdida/neto para columnas con signo mixto
FR36: Epic 9 - Frase explicativa en español simple del desglose
```

## Epic List

### Epic 9: Resumen ejecutivo con múltiples KPIs
Un analista puede fijar varios resúmenes agrupados a la vez (venta por cliente, gasto por tipo de costo, etc.) para verlos juntos en pantalla, y cuando una columna de valor mezcla positivos y negativos, ve el desglose venta/pérdida/neto en vez de un solo número que oculta la pérdida.
**FRs covered:** FR33, FR34, FR35, FR36

## Epic 9: Resumen ejecutivo con múltiples KPIs

Un analista puede fijar varios resúmenes agrupados (ej. "venta por cliente" y "gasto
por tipo de costo") a la vez, viéndolos juntos en pantalla en vez de reemplazándose
uno a otro, y cuando una columna de valor mezcla positivos y negativos, ve el
desglose venta/pérdida/neto en vez de un solo número que oculta la pérdida.

**FRs covered:** FR33, FR34, FR35, FR36 · **UX-DR:** UX-DR6, UX-DR7

### Story 9.1: Fijar varios resúmenes a la vez

As a analista sin conocimientos de Python,
I want generar varios resúmenes agrupados (ej. "venta por cliente" y "gasto por tipo de costo") y verlos todos juntos en pantalla,
So that no tenga que elegir entre mirar uno u otro, perdiendo el anterior cada vez que genero uno nuevo.

**Acceptance Criteria:**

**Given** ya generé un resumen (Story 8.2/8.3)
**When** cambio la selección de columnas y genero un resumen nuevo
**Then** el resumen anterior se queda fijado en pantalla y el nuevo se agrega al lado/debajo, no lo reemplaza.

**Given** tengo uno o más resúmenes fijados
**When** hago clic en "quitar" sobre uno específico
**Then** solo ese desaparece — los demás permanecen intactos, sin regenerarse.

**Given** ya tengo 4 resúmenes fijados (el tope)
**When** intento generar uno más
**Then** el sistema me lo impide con un mensaje claro (ej. "Ya tienes el máximo de 4 resúmenes fijados — quita uno para agregar otro"), sin perder ninguno de los 4 existentes.

**Given** tengo resúmenes fijados
**When** subo un Excel nuevo o reinicio la sesión
**Then** todos los resúmenes fijados se limpian (mismo comportamiento que hoy tiene `summaryResult` al cambiar de perfil) — no quedan resúmenes de un archivo distinto mezclados con el nuevo.

**Given** un resumen fijado es elegible para vista de tarjetas (≤8 categorías, ya establecido)
**When** lo tengo fijado junto a otros
**Then** cada uno mantiene su propio estado de vista (tarjetas o tabla) de forma independiente — cambiar la vista de uno no afecta a los demás.

**Given** un resumen fijado terminó en error (ej. el backend no respondió)
**When** se muestra junto a los demás
**Then** se ve claramente marcado como error sin bloquear ni afectar la visualización de los resúmenes fijados que sí funcionaron.

### Story 9.2: Desglose venta/pérdida/neto cuando el valor tiene signo mixto

As a analista sin conocimientos de Python,
I want que un resumen agrupado me muestre por separado cuánto vendí, cuánto perdí en devoluciones y cuál es mi neto real, cuando esa columna realmente mezcla positivos y negativos,
So that no se me esconda la pérdida detrás de un solo número neto.

**Acceptance Criteria:**

**Given** la columna de valor elegida para el resumen tiene al menos una fila positiva y al menos una fila negativa en todo el archivo
**When** genero el resumen
**Then** cada grupo muestra 3 valores: total positivo ("venta"), total negativo ("pérdida/devolución") y neto (la suma de ambos) — no un solo número.

**Given** la columna de valor elegida es toda positiva (o toda negativa) en todo el archivo — como en el caso real de "detallado comfenalco"
**When** genero el resumen
**Then** se muestra igual que hoy (Story 8.2, un solo total por grupo) — nunca aparece una categoría de "pérdida: $0" fabricada.

**Given** aplica el desglose de signo mixto
**When** se muestra el resumen
**Then** aparece una frase en español simple explicando la relación (ej. "de $X vendidos, $Y volvieron como devolución — tu neto real es $Z"), mismo patrón que `table_explanation.py`.

**Given** un grupo específico, dentro de una columna con signo mixto a nivel de archivo, resulta tener únicamente filas positivas (o únicamente negativas)
**When** se calcula su desglose
**Then** su "pérdida" (o su "venta") se muestra como $0 — un cero real y legítimo para ESE grupo, no una fabricación, porque la columna sí mezcla signos en otras partes del archivo.

**Given** un grupo cuya venta y pérdida se cancelan exactamente (neto = 0)
**When** se muestra
**Then** no aparece "inf"/"nan" en ningún campo — mismo guard de división-por-cero ya establecido en `table_builder.py` (`_pareto_marker_lines`).

**Given** el desglose de signo mixto está activo
**When** se muestra el resumen en vista de tarjetas (Story 9.1 + tarjetas existentes)
**Then** los 3 valores se ven visualmente diferenciados entre sí (no solo como texto corrido) dentro de la misma tarjeta.
