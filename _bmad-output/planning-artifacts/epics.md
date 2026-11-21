---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories']
inputDocuments:
  - 'prd-sico-pandas-lab-2026-07-12.md'
  - 'architecture-sico-pandas-lab-2026-07-12.md'
  - 'analisis-interactividad-ux-guiado-nocode-sico-pandas-lab-2026-09-21.md'
  - 'epics-sico-pandas-lab-2026-07-12.md'
  - 'epics-modulo-nocode-sico-pandas-lab-2026-07-18.md'
  - 'epics-epic9-kpis-ejecutivos-sico-pandas-lab-2026-07-30.md'
  - 'sprint-status-sico-pandas-lab.yaml'
---

# sico-pandas-lab - Epic Breakdown (Épicas 10-11: Interactividad y UX)

Este documento cubre exclusivamente las **Épicas 10 y 11**, nuevas, salidas de la
mesa redonda del 2026-09-21 sobre interactividad y UX del módulo guiado y del
módulo sin código. Las Épicas 1-9 ya existen (ver `epics-sico-pandas-lab-2026-07-12.md`,
`epics-modulo-nocode-sico-pandas-lab-2026-07-18.md` y
`epics-epic9-kpis-ejecutivos-sico-pandas-lab-2026-07-30.md`) y **no se tocan aquí**
— este documento no las duplica, solo asume su numeración para no chocar.

**Nota de alcance:** el PRD y la Arquitectura son del 2026-07-12 y no cubren el
módulo sin código (agregado después, vía documentos de épicas independientes sin
enmienda formal al PRD). Por eso los FR/NFR de abajo son los del proyecto
original (notebook + guiado + acceso a datos); los requisitos específicos de las
Épicas 10 y 11 salen del documento de análisis de la mesa redonda, listados en
la sección UX Design Requirements.

## Requirements Inventory

### Functional Requirements

_(FR1-FR3 movidos a Growth desde el PRD original; se listan FR4-FR21 tal como
existen, para contexto — ninguno se modifica en las Épicas 10/11)_

FR4: Un usuario puede cargar un archivo Excel como fuente de datos para practicar.
FR5: Un usuario puede conectarse al esquema `sco` y ver/seleccionar las tablas disponibles mediante un panel de conexión.
FR6: Un usuario puede cargar los datos de una o varias tablas de la base de datos como un DataFrame de pandas dentro de su notebook.
FR6b: Un usuario puede ejecutar consultas combinadas (joins) entre dos, tres o las tablas que requiera del esquema `sco`.
FR7: El sistema impide cualquier operación de escritura sobre la base de datos de producción.
FR8: Un usuario puede crear y editar celdas de código Python/pandas.
FR9: Un usuario puede ejecutar una celda de código de forma individual y ver su resultado (tabla, texto, error o gráfica).
FR10: Un usuario puede ejecutar celdas en el orden que elija dentro de su sesión.
FR11: Un usuario puede ver mensajes de error claros cuando su código falla, sin que la sesión se rompa.
FR12: Un usuario puede generar gráficas (líneas, barras, dispersión, histogramas, etc.) a partir de un DataFrame.
FR13: Un usuario puede reiniciar su notebook/sesión para empezar de nuevo.
FR14: Un usuario puede acceder a un módulo guiado con ejemplos paso a paso usando datos reales de sico.
FR15: El módulo guiado explica qué hace cada bloque de código pandas mostrado.
FR16: Un usuario puede ejecutar los ejemplos del módulo guiado por su cuenta, celda por celda.
FR17: Un usuario puede pasar del módulo guiado al notebook de práctica libre.
FR18: El sistema ejecuta el código de cada usuario en un entorno aislado (sandbox) por sesión.
FR19: El sistema impone límites de tiempo y recursos por ejecución de celda.
FR20: Las credenciales de conexión a la base de datos nunca son visibles ni accesibles desde el código del usuario.
FR21: El sistema verifica automáticamente al arrancar los privilegios de solo-lectura.

**Requisitos funcionales nuevos para este documento (derivados del análisis de mesa redonda, sin FR# del PRD original porque el módulo sin código no está en el PRD):**

FR-NC1 (existente, Épica 5): un usuario puede generar una gráfica sin código a partir de columnas confirmadas de su Excel.
FR-NC2 (existente, Épica 8): el sistema calcula y muestra un resumen Pareto con % acumulado.
FR-G1 (existente, Épica 3): un usuario ve retos verificados en servidor dentro del módulo guiado.

### NonFunctional Requirements

NFR1 (Security): las credenciales de la RDS nunca se exponen al código del usuario ni al frontend — sin cambios para Épicas 10/11.
NFR2 (Performance): sin objetivo formal de tiempo de respuesta más allá de "segundos, no romper el flujo" — aplica también a la carga de Chart.js (no debe percibirse un retraso notable al renderizar el tablero).
NFR3 (Scalability): explícitamente no es prioridad (2-3 usuarios) — Épicas 10/11 no cambian este supuesto.
NFR4 (Accessibility): nivel básico razonable (contraste, navegación por teclado), sin objetivo formal WCAG — aplica a los nuevos componentes visuales (mapa de lecciones, tooltips de gráfica) tanto como al resto de la app.
NFR5 (Reliability): errores deben mostrarse claros, sin exponer detalles técnicos — aplica si Chart.js falla al renderizar (debe degradar a mensaje claro, no pantalla en blanco).

### Additional Requirements

_(de Architecture 2026-07-12, más contexto de las épicas 4-9 ya implementadas)_

- Wrapper de respuesta `ApiResponse` (`{ message, data, success, status }`) obligatorio en toda respuesta backend nueva — Épica 10 debe usarlo si expone un endpoint nuevo o extiende uno existente para servir datos crudos de gráfica.
- Frontend: NgModules por feature (no standalone), sin NgRx, servicios Angular + RxJS para estado — cualquier estado nuevo de Chart.js o del mapa de lecciones sigue este patrón, no introduce un store nuevo.
- **Decisión de Arquitectura ya escrita (2026-07-12, sección Growth):** "Gráficas interactivas (Plotly/Bokeh) quedan como posible mejora de Growth" — **actualización de la mesa redonda (2026-09-21):** se elige Chart.js en vez de Plotly por peso de bundle (~60KB vs ~1MB) dado que `frontend/package.json` no tiene ninguna librería de gráficos instalada todavía. Esto debe reflejarse como actualización a la Arquitectura, no como decisión nueva sin precedente.
- `backend/app/notebook/execution.py` ya expone `result_records` (agregado para las tarjetas KPI de resúmenes de baja cardinalidad, 2026-07-30) — Épica 10 extiende este mecanismo para los bloques de tipo gráfica del módulo sin código, en vez de crear un mecanismo paralelo.
- El notebook libre (`backend/app/notebook/chart_builder.py`, SVG/matplotlib server-side) **no se modifica** — la interactividad de Épica 10 aplica solo al tablero automático del módulo sin código (`analysis-dashboard.component`, `no-code-chart.component`).
- `backend/app/guided/data_context.py` ya decide si una lección usa datos reales de SICO o ejemplo sintético — Épica 11 solo expone ese dato existente al frontend, no requiere lógica nueva de backend para ese punto.
- Design tokens compartidos en `frontend/src/styles.scss` (`var(--token)`) — cualquier color nuevo (tema de Chart.js, estados del mapa de lecciones) debe leerse de ahí, no declarar colores sueltos (regla explícita del README del repo).

### UX Design Requirements

_(no existe un DESIGN.md/EXPERIENCE.md formal de `bmad-ux` en este proyecto — estos UX-DR salen del documento de análisis de la mesa redonda `analisis-interactividad-ux-guiado-nocode-sico-pandas-lab-2026-09-21.md`, tratado como el contrato de UX disponible)_

**Épica 10 — Gráficos interactivos (módulo sin código):**

UX-DR1: Al pasar el mouse sobre una barra/segmento de una gráfica del tablero automático, se muestra un tooltip con el valor exacto y el % acumulado (si aplica).
UX-DR2: La gráfica anima su entrada al renderizarse (no aparece de golpe).
UX-DR3: El Pareto marca visualmente la línea de corte del 80% acumulado como anotación sobre la gráfica.
UX-DR4: Los colores de la gráfica usan los `--token` de `styles.scss` — ningún color hardcodeado nuevo.
UX-DR5 (exclusión explícita): el notebook libre sigue generando su gráfica como imagen server-side (SVG/matplotlib) sin ningún cambio de comportamiento ni de UI.

**Épica 11 — Progreso y feedback (módulo guiado):**

UX-DR6: `guided-home` muestra las 6 lecciones como un mapa/camino con 3 estados visuales distinguibles: completada, actual, bloqueada (no una lista vertical plana).
UX-DR7: Al superar un reto en `guided-lesson`, aparece una transición y un micro-mensaje contextual, visualmente distinto del resultado crudo de una celda ejecutada sin más.
UX-DR8: Cada tarjeta de lección indica si usa datos reales de SICO o un ejemplo sintético.

**Transversal (criterio de aceptación dentro de 10 y 11, no épica aparte):**

UX-DR9: Pulido visual general — micro-interacciones y estados vacíos con más carácter — se exige como criterio de aceptación en las historias de ambas épicas, no queda como trabajo sin dueño.

**Explícitamente fuera de alcance para este corte (candidata a Épica 12 futura):**

UX-DR10 (descartado por ahora): racha/gamificación de sesión en el módulo guiado — requiere lógica de tiempo/sesión inexistente hoy y una decisión de diseño no resuelta (motiva vs. desincentiva uso esporádico).

### FR Coverage Map

FR-NC1: Epic 10 - gráfica sin código, ahora con datos crudos en vez de solo imagen
FR-NC2: Epic 10 - resumen Pareto, ahora con anotación visual del 80%
UX-DR1: Epic 10 - tooltip con valor y % acumulado
UX-DR2: Epic 10 - animación de entrada
UX-DR3: Epic 10 - línea de corte del 80% como anotación
UX-DR4: Epic 10 - colores desde design tokens
UX-DR5: Epic 10 - exclusión explícita del notebook libre (criterio de no-regresión)
FR-G1: Epic 11 - retos verificados, ahora con feedback visual diferenciado
UX-DR6: Epic 11 - mapa de lecciones tipo camino
UX-DR7: Epic 11 - transición + micro-mensaje al superar un reto
UX-DR8: Epic 11 - indicador de datos reales SICO vs. sintético
UX-DR9: Epic 10 + Epic 11 - pulido visual como criterio de aceptación transversal
UX-DR10: Sin epic - descartado para este corte, candidato a Épica 12

## Epic List

### Epic 10: Gráficos interactivos en el módulo sin código

Quien sube un Excel y llega al tablero automático puede explorar sus gráficas
con tooltip (valor + % acumulado), animación de entrada y la línea de corte
del 80% marcada — en vez de ver una imagen estática sin interacción.

**FRs covered:** FR-NC1, FR-NC2 (extendidas), UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR5 (exclusión explícita del notebook libre), UX-DR9 (parcial)

### Epic 11: Progreso y feedback en el módulo guiado

Quien avanza por las 6 lecciones ve su progreso en un mapa visual con estados
claros, recibe una reacción distinta cuando supera un reto (no solo el
resultado crudo de una celda), y sabe si trabaja con sus propios datos de SICO
o un ejemplo sintético.

**FRs covered:** FR-G1 (extendida), UX-DR6, UX-DR7, UX-DR8, UX-DR9 (parcial)

**Nota:** ninguna dependencia entre Epic 10 y Epic 11. Ambas asumen Épicas 3 y
4-8 ya implementadas (lo están). UX-DR10 (racha/gamificación) queda fuera de
ambas — candidata a una futura Épica 12.

## Epic 10: Gráficos interactivos en el módulo sin código

Quien sube un Excel y llega al tablero automático puede explorar sus gráficas
con tooltip (valor + % acumulado), animación de entrada y la línea de corte
del 80% marcada — en vez de ver una imagen estática sin interacción.

**FRs covered:** FR-NC1, FR-NC2 (extendidas), UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR5, UX-DR9 (parcial)

### Story 10.1: Migrar el tablero automático a gráficas interactivas con datos crudos

Como desarrollador,
quiero que el backend sirva los datos crudos de cada bloque de gráfica del tablero automático (extendiendo `result_records`) y que el frontend los renderice con Chart.js,
para reemplazar la imagen SVG estática por una gráfica interactiva real, base para el resto de las mejoras de la Épica 10.

**Acceptance Criteria:**

**Given** un bloque de tipo gráfica del tablero automático
**When** el backend arma la respuesta de ese bloque
**Then** incluye los datos crudos (categorías, valores, acumulado si aplica), siguiendo el wrapper `ApiResponse` existente
**And** el frontend renderiza esos datos con Chart.js en vez de inyectar un SVG
**And** el notebook libre (`chart_builder.py`, SVG server-side) no cambia su comportamiento ni su contrato de respuesta — criterio de no-regresión (UX-DR5)

### Story 10.2: Ver tooltip con valor exacto en las gráficas

Como usuario que subió un Excel al módulo sin código,
quiero ver un tooltip con el valor exacto (y el % acumulado cuando aplique) al pasar el mouse sobre una barra/segmento,
para leer el dato preciso sin adivinarlo desde la altura de la barra.

**Acceptance Criteria:**

**Given** una gráfica del tablero automático ya renderizada con Chart.js (Story 10.1)
**When** paso el mouse sobre una barra
**Then** veo un tooltip con el valor exacto
**And** si la gráfica es un Pareto, el tooltip también muestra el % acumulado hasta ese punto
**And** en un dispositivo táctil (sin hover), el tooltip aparece al tocar la barra

### Story 10.3: Animación de entrada al generar una gráfica

Como usuario del módulo sin código,
quiero que la gráfica anime su entrada al generarse,
para que el tablero se sienta vivo en vez de aparecer de golpe.

**Acceptance Criteria:**

**Given** que confirmé mis columnas y el sistema generó el tablero (Story 10.1)
**When** la gráfica se renderiza por primera vez
**Then** las barras/segmentos animan su entrada en menos de 1 segundo
**And** si regenero la misma gráfica (cambio de columna), la animación se repite sin duplicar elementos visuales

### Story 10.4: Línea de corte del 80% en el Pareto

Como usuario que genera un resumen Pareto,
quiero ver marcada la línea donde se cruza el 80% acumulado,
para identificar de un vistazo qué categorías concentran la mayoría del valor.

**Acceptance Criteria:**

**Given** un resumen Pareto con % acumulado calculado (Épica 8) ya renderizado con Chart.js (Story 10.1)
**When** se renderiza la gráfica interactiva
**Then** aparece una anotación (línea + etiqueta "80%") donde el acumulado cruza ese umbral
**And** la anotación usa el color de énfasis de los design tokens, no un color nuevo

### Story 10.5: Colores del gráfico alineados a los design tokens

Como usuario de cualquier módulo de la app,
quiero que los colores de las gráficas interactivas coincidan con la paleta del resto de la app,
para que el tablero se sienta parte de la misma herramienta.

**Acceptance Criteria:**

**Given** el tema de Chart.js configurado en el frontend
**When** se renderiza cualquier gráfica del tablero automático
**Then** los colores provienen de los `--token` de `styles.scss`, no de valores hardcodeados

## Epic 11: Progreso y feedback en el módulo guiado

Quien avanza por las 6 lecciones ve su progreso en un mapa visual con estados
claros, recibe una reacción distinta cuando supera un reto (no solo el
resultado crudo de una celda), y sabe si trabaja con sus propios datos de SICO
o un ejemplo sintético.

**FRs covered:** FR-G1 (extendida), UX-DR6, UX-DR7, UX-DR8, UX-DR9 (parcial)

### Story 11.1: Ver el progreso de las 6 lecciones como un mapa

Como usuario del módulo guiado,
quiero ver mis 6 lecciones como un mapa/camino con estados claros (completada, actual, bloqueada),
para entender de un vistazo cuánto llevo y qué sigue.

**Acceptance Criteria:**

**Given** que tengo al menos una lección completada y otras pendientes
**When** entro a `guided-home`
**Then** veo las 6 lecciones conectadas visualmente, cada una con su estado distinguible sin leer texto
**And** la lección marcada "actual" es la primera no completada en la secuencia
**And** si una lección tiene prerequisito no cumplido, se muestra bloqueada (no clickeable o con aviso claro)

### Story 11.2: Feedback distinto al superar un reto

Como usuario resolviendo un reto del módulo guiado,
quiero una reacción visual clara y distinta cuando mi código pasa la validación del servidor,
para saber inequívocamente que lo logré, no solo que mi código corrió sin error.

**Acceptance Criteria:**

**Given** que ejecuté una celda cuyo reto tiene validación en `challenges.py`
**When** el servidor confirma que el reto se superó
**Then** veo una transición y un micro-mensaje contextual, distinto del resultado crudo de una celda cualquiera
**And** si el código corre sin error pero no cumple el reto, veo el resultado normal sin el feedback de "reto superado"
**And** este feedback envuelve `cell-result.component`, no lo reemplaza

### Story 11.3: Indicador de datos reales de SICO vs. ejemplo sintético

Como usuario del módulo guiado,
quiero ver en cada tarjeta de lección si voy a trabajar con datos reales de SICO o con un ejemplo sintético,
para entender por qué una lección se siente distinta de otra y valorar cuando son mis propios datos.

**Acceptance Criteria:**

**Given** que ya subí un Excel o tengo datos reales disponibles para al menos una lección
**When** veo el mapa de lecciones
**Then** cada tarjeta indica "tus datos" o "ejemplo"
**And** ese dato viene de `data_context.py` existente, sin lógica nueva de backend
