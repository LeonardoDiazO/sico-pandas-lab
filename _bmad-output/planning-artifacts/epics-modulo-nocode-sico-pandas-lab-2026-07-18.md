---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete'
completedAt: '2026-07-20'
inputDocuments: ['prd-sico-pandas-lab-2026-07-12.md', 'architecture-sico-pandas-lab-2026-07-12.md', 'analisis-modulo-nocode-sico-pandas-lab-2026-07-18.md', 'GUIA_PRACTICA_FACTURAS_MATECOL.md']
continuesFrom: 'epics-sico-pandas-lab-2026-07-12.md (Épicas 1-3, ya implementadas — no se tocan aquí)'
---

# sico-pandas-lab (módulo sin código) - Epic Breakdown

This document provides the complete epic and story breakdown for the "módulo sin
código" of sico-pandas-lab, decomposing the requirements from the PRD, the
no-code module analysis, and the Architecture requirements into implementable
stories. No formal UX Design document exists for this project; the UX-DR items
below are derived from the party-mode analysis (`analisis-modulo-nocode-...md`)
instead.

## Requirements Inventory

### Functional Requirements

**Nota de alcance:** FR1-FR21 (login, conexión a datos existente, notebook libre,
módulo guiado, seguridad de ejecución, administración) pertenecen a las Épicas
1-3, ya implementadas — ver `epics-sico-pandas-lab-2026-07-12.md`. Este documento
solo cubre los FR nuevos del módulo "sin código".

FR22: Al subir un Excel, el sistema lo perfila (detecta fila de encabezado real, tipo de dato por columna) y devuelve un veredicto: usable / usable_con_limpieza / no_usable.
FR23: Cuando el veredicto es usable_con_limpieza, el sistema muestra una vista previa de la limpieza propuesta (fila de encabezado detectada + columnas encontradas) para que el usuario la confirme.
FR24: Cuando el veredicto es no_usable, el sistema explica claramente por qué el archivo no sirve, sin error técnico genérico.
FR25: Un usuario puede elegir, en un combo/select, una columna categórica o de fecha del Excel cargado para agrupar/graficar por ella.
FR26: Un usuario puede elegir, en un combo/select, un tipo de gráfica (torta, barras, histograma, línea) entre las opciones compatibles con la columna elegida en FR25.
FR27: El sistema genera la gráfica elegida sin que el usuario escriba código, reutilizando el motor de ejecución del notebook existente.
FR28: El sistema advierte al usuario cuando la columna elegida tiene cardinalidad demasiado alta para producir una gráfica legible, antes de generarla.
FR29 (evaluar después de uso real de FR25-28): Un usuario puede escribir una petición en lenguaje natural (ej. "hazme una torta por vendedor") y el sistema la traduce a una selección de columna + tipo de gráfica dentro de las opciones ya definidas por FR25/FR26 — nunca genera ni ejecuta pandas arbitrario a partir de esa entrada.

### NonFunctional Requirements

**Nota de alcance:** NFR1-NFR9 pertenecen a las Épicas 1-3 (ver documento anterior).

NFR10 (Security, no negociable): FR29 tiene prohibido por diseño generar/ejecutar código pandas arbitrario; su única salida permitida es una selección entre opciones cerradas ya validadas por el perfilador (FR22).
NFR11 (Cost/Integration): las llamadas al proveedor de LLM para FR29 envían solo metadatos de columnas (nombres/tipos), nunca el contenido real del Excel, y están limitadas por sesión (servicio sin autenticación).
NFR12 (Performance): el perfilado (FR22) y la generación dinámica de gráficas (FR27) respetan el mismo límite de tiempo ya definido para celdas del notebook (`CELL_TIMEOUT_SECONDS`).

### Additional Requirements

- No se instala librería de gráficas nueva en Angular (Chart.js/ECharts) para este MVP — se reutiliza el motor matplotlib server-side existente (`backend/app/notebook/execution.py`), consistente con la decisión ya registrada en la Arquitectura de dejar gráficas interactivas (Plotly) fuera del MVP.
- El módulo de perfilado (`excel_profiler`) envuelve, no reemplaza, `backend/app/data_access/excel_loader.py`.
- FR29 requiere secreto de API de LLM como variable de entorno de backend, nunca expuesto al frontend.
- La épica del bot (FR29) se secuencia después de tener datos de uso real de la épica de gráficas sin código — no se construye en paralelo.
- Caso de prueba de referencia obligatorio para FR22/FR23: `relacion de facturas matecol.xlsx` (342 filas totales, 171 facturas reales, documentado en `GUIA_PRACTICA_FACTURAS_MATECOL.md`).

### UX Design Requirements

UX-DR1: El resultado de la validación del Excel se muestra como uno de 3 estados visuales distintos (usable / usable con limpieza / no usable) — nunca como un error genérico.
UX-DR2: Cuando el veredicto es "usable_con_limpieza", se muestra una vista previa confirmable (fila de encabezado + columnas detectadas) antes de proceder — no una limpieza silenciosa.
UX-DR3: El selector de tipo de gráfica se filtra dinámicamente según el tipo de columna elegida en el primer selector — nunca se muestran combinaciones inválidas.

### FR Coverage Map

```
FR22: Epic 4 - Perfilar Excel al subir (fila de encabezado, tipos de columna)
FR23: Epic 4 - Vista previa confirmable de limpieza propuesta
FR24: Epic 4 - Mensaje claro cuando el Excel no sirve
FR25: Epic 5 - Selector de columna para agrupar/graficar
FR26: Epic 5 - Selector de tipo de gráfica compatible
FR27: Epic 5 - Generar gráfica sin código, motor existente
FR28: Epic 5 - Advertencia de cardinalidad alta antes de graficar
FR29: Epic 6 - Traducir lenguaje natural a selección cerrada de columna+gráfica
```

## Epic List

### Epic 4: Perfilado y validación de Excel al subir
El usuario sube cualquier Excel y sabe de inmediato si sirve para graficar — y si no sirve "tal cual", ve qué se puede arreglar y lo confirma con un clic, en vez de un error genérico.
**FRs covered:** FR22, FR23, FR24
**NFRs/otros:** NFR12 (límite de tiempo), UX-DR1, UX-DR2
**Nota de implementación:** envuelve `excel_loader.py`, no lo reemplaza. Caso de prueba obligatorio: `relacion de facturas matecol.xlsx`.

### Epic 5: Gráficas sin código (combo-select dinámico)
El usuario, sin escribir una línea de Python, elige una columna y un tipo de gráfica y obtiene la imagen — para cualquier Excel que haya subido, no solo el de Matecol. Depende de que Epic 4 ya haya perfilado el archivo, pero entrega un resultado completo por sí sola.
**FRs covered:** FR25, FR26, FR27, FR28
**NFRs/otros:** NFR12, UX-DR3
**Nota de implementación:** reutiliza `backend/app/notebook/execution.py` (matplotlib server-side) — cero librería de charts nueva en Angular para este MVP.

### Epic 6: Asistente en lenguaje natural (bot)
El usuario escribe una pregunta de negocio en texto libre y el sistema la traduce a la selección de columna+gráfica que Epic 5 ya sabe ejecutar — nunca genera ni ejecuta pandas libre. Se evalúa y prioriza solo después de tener uso real de Epic 5.
**FRs covered:** FR29
**NFRs/otros:** NFR10 (no negociable), NFR11

## Epic 4: Perfilado y validación de Excel al subir

El usuario sube cualquier Excel y el sistema le dice de inmediato si sirve para
graficar — con guía para arreglarlo si no sirve tal cual. **FRs:** FR22, FR23,
FR24 | **NFRs:** NFR12 | **UX-DR:** UX-DR1, UX-DR2

### Story 4.1: Perfilar el Excel al subirlo

As a usuario sin conocimientos de Python,
I want que el sistema analice mi Excel apenas lo subo,
So that sepa de inmediato si sirve para graficar sin tener que adivinarlo.

**Acceptance Criteria:**

**Given** subo un archivo .xlsx o .xls válido
**When** el sistema lo procesa
**Then** detecta la fila donde realmente empieza la tabla de datos (no necesariamente la fila 1) e infiere el tipo de cada columna (categórica, numérica, fecha, o descartable)
**And** devuelve uno de tres veredictos: `usable`, `usable_con_limpieza`, o `no_usable`

**Given** subo `relacion de facturas matecol.xlsx` (el reporte crudo de SICO con metadata y subtotales intercalados)
**When** el sistema lo perfila
**Then** el veredicto es `usable_con_limpieza`, detecta la fila de encabezado real, y las 171 filas de facturas reales quedan identificadas — igual que la limpieza manual documentada en `GUIA_PRACTICA_FACTURAS_MATECOL.md`
**And** el perfilado completo respeta el límite de tiempo de `CELL_TIMEOUT_SECONDS` (NFR12), sin colgar la sesión con archivos grandes

### Story 4.2: Confirmar la limpieza propuesta cuando el Excel viene sucio

As a usuario sin conocimientos de Python,
I want ver qué limpieza propone el sistema antes de que se aplique,
So that no me quede preguntándome qué le hizo a mis datos.

**Acceptance Criteria:**

**Given** el veredicto del perfilado (Story 4.1) es `usable_con_limpieza`
**When** el sistema me lo muestra
**Then** veo una vista previa con la fila de encabezado detectada y la lista de columnas encontradas (UX-DR2), no una limpieza silenciosa
**And** tengo un botón para confirmar y continuar, o cancelar y subir otro archivo

**Given** confirmo la vista previa
**When** el sistema aplica la limpieza
**Then** el DataFrame resultante queda disponible para la Épica 5 (selección de columna + gráfica), con los mismos tipos de columna ya inferidos

### Story 4.3: Ver un mensaje claro cuando el Excel no sirve

As a usuario sin conocimientos de Python,
I want entender por qué mi archivo no se puede usar,
So that sepa qué corregir en vez de recibir un error técnico que no entiendo.

**Acceptance Criteria:**

**Given** el veredicto del perfilado (Story 4.1) es `no_usable` (ej. archivo vacío, sin filas suficientes, o sin ninguna columna categórica/numérica reconocible)
**When** el sistema me lo muestra
**Then** veo un mensaje en lenguaje simple explicando qué falta (UX-DR1) — nunca un stacktrace ni un error genérico
**And** puedo subir otro archivo sin recargar la página

## Epic 5: Gráficas sin código (combo-select dinámico)

El usuario, sin escribir una línea de Python, elige una columna y un tipo de
gráfica y obtiene la imagen — para cualquier Excel que haya subido. **FRs:**
FR25, FR26, FR27, FR28 | **NFRs:** NFR12 | **UX-DR:** UX-DR3

### Story 5.1: Elegir la columna para agrupar

As a usuario sin conocimientos de Python,
I want ver un selector con las columnas de mi Excel que tienen sentido para agrupar,
So that no tenga que adivinar cuáles de mis columnas sirven para eso.

**Acceptance Criteria:**

**Given** mi Excel ya fue perfilado y confirmado (Epic 4, veredicto `usable` o `usable_con_limpieza` confirmado)
**When** abro el selector de columna
**Then** solo veo las columnas categóricas o de fecha (FR25) — las numéricas (ej. `neto`) no aparecen ahí, porque agrupar por un valor numérico no tiene sentido
**And** cada opción muestra el nombre real de la columna detectado en el perfilado (ej. "Vdor", "Bod", no "Unnamed: 4")

### Story 5.2: Elegir el tipo de gráfica compatible

As a usuario sin conocimientos de Python,
I want que el segundo selector solo me muestre gráficas que tienen sentido con la columna que elegí,
So that no arme una combinación que no se pueda graficar.

**Acceptance Criteria:**

**Given** ya elegí una columna en el selector de la Story 5.1
**When** abro el selector de tipo de gráfica
**Then** solo veo los tipos compatibles (UX-DR3): torta y barras si la columna es categórica, línea si es de fecha, histograma solo si además elijo una columna numérica de valor
**And** si cambio la columna elegida, las opciones de este segundo selector se actualizan automáticamente

### Story 5.3: Generar la gráfica sin escribir código

As a usuario sin conocimientos de Python,
I want que al confirmar columna + tipo de gráfica el sistema me muestre la imagen,
So that pueda ver el resultado sin tocar una celda de código.

**Acceptance Criteria:**

**Given** elegí una columna (5.1) y un tipo de gráfica compatible (5.2)
**When** confirmo la selección
**Then** el sistema genera la gráfica reutilizando el motor de ejecución existente (`backend/app/notebook/execution.py`, matplotlib server-side) y me la muestra como imagen (FR27)
**And** la generación respeta el límite de tiempo definido por `CELL_TIMEOUT_SECONDS` (NFR12)

**Given** ya generé una gráfica
**When** quiero generar otra con una columna o tipo distinto
**Then** puedo hacerlo sin volver a subir el Excel (reutiliza el DataFrame ya perfilado de la sesión)

### Story 5.4: Advertencia por cardinalidad alta

As a usuario sin conocimientos de Python,
I want que el sistema me avise si mi elección va a producir una gráfica ilegible,
So that no piense que rompí algo cuando en realidad la gráfica no tenía cómo verse bien.

**Acceptance Criteria:**

**Given** elegí una columna con demasiados valores únicos para el tipo de gráfica seleccionado (ej. `No.Factura` con 171 valores distintos para una torta)
**When** intento generarla
**Then** el sistema me advierte antes de generarla (FR28) y sugiere agrupar en "top N + otros" o elegir otra columna
**And** si insisto en generarla igual, puedo hacerlo, pero la advertencia quedó explícita primero

## Epic 6: Asistente en lenguaje natural (bot)

El usuario escribe una pregunta de negocio en texto libre y el sistema la
traduce a la selección de columna+gráfica que Epic 5 ya sabe ejecutar — nunca
genera ni ejecuta pandas libre. Se evalúa solo después de tener uso real de
Epic 5. **FRs:** FR29 | **NFRs:** NFR10 (no negociable), NFR11

### Story 6.1: Traducir una pregunta en lenguaje natural a la selección de gráfica

As a usuario sin conocimientos de Python,
I want escribirle al asistente algo como "hazme una torta por vendedor" en vez de usar los dos selectores,
So that no tenga que saber en qué columna vive la respuesta a mi pregunta.

**Acceptance Criteria:**

**Given** ya subí y confirmé un Excel (Epic 4)
**When** le escribo al asistente una petición en lenguaje natural
**Then** el sistema la traduce a una combinación válida de `{columna, tipo_de_gráfica}` tomada exclusivamente de las opciones que Epic 5 ya expone para ese Excel (FR29)
**And** el asistente nunca genera ni ejecuta código pandas a partir de mi texto — solo elige entre el menú cerrado ya validado (NFR10, no negociable)

**Given** mi petición no tiene una combinación válida dentro del menú cerrado (ej. "compárame julio contra junio")
**When** el asistente no puede resolverla con una sola selección
**Then** me lo dice claramente y me sugiere usar los selectores manuales de Epic 5, en vez de inventar una respuesta o intentar generar código

### Story 6.2: Límite de uso del asistente por sesión

As a operador de la app (dueño del producto),
I want que el asistente tenga un límite de uso por sesión,
So that el costo del proveedor de LLM no se dispare en un servicio público sin login.

**Acceptance Criteria:**

**Given** la app no tiene autenticación y está desplegada públicamente en Render
**When** una sesión usa el asistente repetidamente
**Then** el sistema aplica un límite de peticiones por sesión (NFR11) y lo comunica claramente si se alcanza
**And** cada petición al LLM envía solo metadatos de columnas (nombres/tipos), nunca el contenido real de los datos del Excel
