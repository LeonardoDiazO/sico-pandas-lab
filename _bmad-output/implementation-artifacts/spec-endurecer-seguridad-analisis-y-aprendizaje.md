---
title: 'Endurecer seguridad, corregir el análisis y conectar el aprendizaje'
type: 'feature'
created: '2026-11-18'
status: 'done'
baseline_commit: 'c7634ccf176127e1747144616d730a9f92b64112'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture-sico-pandas-lab-2026-07-12.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La auditoría del 2026-11-18 encontró que (1) el Notebook ejecuta Python con builtins completos, sin acceso controlado, sin tope de sesiones ni de tamaño de archivo, y con el id de sesión elegido por el cliente — cualquiera con la URL lee `GEMINI_API_KEY`; (2) el análisis automático da resultados engañosos (dinero detectado por subcadena, solo suma, negativos, solo primera hoja, "(vacío)" como categoría, dimensiones grandes excluidas, fecha sin uso); (3) no muestra calidad de datos, tendencia ni cruces; (4) el módulo sin código no enseña el pandas que usa y solo 2 de 6 lecciones tienen reto, trampeable.

**Approach:** Un solo entregable en cuatro capas que el usuario pidió mantener juntas: endurecer el backend (entorno limpio en el worker, allowlist de imports, tope de sesiones, sesión emitida por el servidor, límite de subida, consentimiento IA), corregir y ampliar el catálogo automático, y unir sin-código con aprendizaje ("Ver el código", retos en todas las lecciones verificados contra una copia intocable, 3 lecciones nuevas).

**Decisiones (2026-11-18, del usuario):**
1. **Acceso:** clave de equipo compartida `APP_ACCESS_KEY` (variable de entorno). Sin clave válida no se ejecuta código ni se sube archivo; pantalla "Ingresa la clave del equipo". Si la variable no está definida (desarrollo local), no se exige.
2. **IA:** confirmación por acción. La clasificación sigue automática pero envía solo nombres y tipos (sin `sampleValues`). La narrativa Pareto exige confirmar en un diálogo que dice cuántas filas/grupos y qué columnas se envían.
3. **Negativos:** Pareto sobre totales netos por grupo; grupos con neto ≤ 0 salen del ranking y se listan aparte con su monto.
4. **Hojas:** al subir se perfilan todas las hojas (filas, columnas, encabezado, veredicto) y el usuario elige cuáles incluir (multi-selección, todas las usables marcadas por defecto). Las elegidas se apilan en un solo `df` con columna `Hoja` (rol dimensión). Si sus columnas difieren, se avisa y se usan solo las comunes, con opción de quitar esa hoja. Con una sola hoja no se muestra el paso.

## Boundaries & Constraints

**Always:** pandas determinista hace todo cálculo, la IA solo clasifica/redacta; contrato `ApiResponse` (`app/utils/api_response.py`) en toda respuesta nueva, incluidos 413/429/503; mismos nombres/semántica de `% del total`, `% acumulado`, `80/20`; cada regla de dinero cambiada en Python se replica en `money-format.ts`; tokens de `styles.scss` en todo estilo nuevo; tests nuevos para cada bug corregido; documentar en `worker.py` que el sandbox protege contra accidentes y abuso casual, no contra un atacante decidido (arquitectura, Decisión #1).

**Never:** Flask-Login/SQLite completos (siguen en Growth); migrar a contenedores/gVisor; mandar el DataFrame completo a Gemini sin consentimiento explícito de esa acción; romper los callers existentes de `build_summary_code`/`build_summary_detail_code`/`_pareto_marker_lines` (parámetros nuevos con default); tocar el módulo Convatec desconectado.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Leer secretos | celda `import os; os.environ` | bloqueado | error claro "import no permitido en este entorno" |
| Secretos vía pandas | celda `pd.io.common.os.environ` | sin `GEMINI_API_KEY` ni `SICO_DB_*` (entorno del worker limpio) | N/A |
| Capacidad | sesión nueva con N≥`MAX_SESSIONS` activas | no se crea worker | 503 "servidor lleno, intenta en unos minutos" |
| Archivo grande | subida > `MAX_UPLOAD_MB` | rechazada antes de parsear | 413 con el límite en el mensaje |
| Dinero falso | columna `Inventario`, `Clientes activa` | no se formatea como pesos | N/A |
| Promedio | métrica marcada "Promedio" | Pareto sobre la media por grupo, título "Promedio de X por Y" | N/A |
| Negativos | métrica con notas crédito | Pareto sobre netos; grupos con neto ≤ 0 listados aparte con su monto | N/A |
| Varias hojas | libro con 3 hojas, usuario elige 2 | se apilan con columna `Hoja` | columnas distintas: aviso + solo columnas comunes |
| Sin clave | `APP_ACCESS_KEY` definida, petición sin clave a execute/upload | rechazada | 401 "Ingresa la clave del equipo" |
| "(vacío)" | dimensión con nulos | grupo fuera del ranking, mostrado aparte con su total | N/A |
| Alta cardinalidad | dimensión con 88 valores | tarjeta Top 15 + "Otros (73)", sin omitirla | N/A |
| Reto trampeado | alumno reemplaza `df` y luego asigna la respuesta | reto no pasa | mensaje: "compara contra los datos originales" |

</frozen-after-approval>

## Code Map

- `backend/app/notebook/worker.py:39-46` -- `worker_loop`: limpiar `os.environ` antes de `build_namespace` (defensa en profundidad, NO suficiente sola: ver Design Notes "Secretos"); `bind` (:81-84) guarda `_pristine[name]=df.copy()` fuera del namespace; rama `check` (:87-93) pasa `_pristine` al checker. Las tablas sintéticas de lección NO se capturan "la primera vez que aparecen": ver Design Notes "Copia prístina".
- `backend/app/notebook/worker_manager.py:35,80` -- `ctx.Process(...).start()`: el hijo debe nacer con entorno sin secretos (ver Design Notes "Secretos").
- `backend/app/config.py` + `backend/app/__init__.py` -- secretos (`SECRET_KEY`, `APP_ACCESS_KEY`, `GEMINI_API_KEY`, `SICO_DB_*`) se leen dentro de `create_app()`, nunca como atributos de clase evaluados al importar (el worker importa el paquete `app`).
- `backend/app/notebook/nl_chart_interpreter.py` (`_default_client`), `pareto_narrative.py`, `semantic_classifier.py`, `data_access/sico_client.py:56-87` -- hoy leen secretos de `os.environ` (o el SDK los toma implícitamente); pasan a leerlos de `current_app.config` (capturados en `create_app`).
- `backend/app/notebook/execution.py:21-45` -- `build_namespace`: reemplazar `__builtins__` por copia con `__import__` filtrado (solo imports de nivel superior desde `<celda>`; permitidos pandas/numpy/matplotlib/seaborn/scipy/math/statistics/datetime/re/json/collections/itertools/urllib.parse) y sin `open`/`exec`/`eval`/`compile`/`input`/`breakpoint`. `import urllib.parse` debe ligar solo el submódulo `parse` (no el paquete `urllib`, que expone `urllib.request`). Además, neutralizar E/S de archivos/URL/pickle de pandas, numpy y matplotlib en el proceso worker (ver Design Notes "E/S").
- `backend/app/notebook/worker_manager.py:24-28,70-96,158-167` -- defaults y `_get_or_create`: `MAX_SESSIONS`; nueva `CapacityError`; `check_and_increment_assistant_usage` (:126) gana un tope global diario además del de sesión.
- `backend/app/__init__.py:15-25,59` + `config.py` -- `MAX_CONTENT_LENGTH`, handlers 413/503 vía `api_response`, middleware de clave de acceso y emisión de sesión firmada (`itsdangerous`, ya viene con Flask) en header `X-Session-Id` de respuesta; rutas leen id solo si la firma es válida, nunca `"anonymous"`.
- `backend/app/notebook/routes.py:37-42`, `guided/routes.py:15-18`, `data_access/routes.py:18-23` -- `_session_id()` duplicado: unificar en `app/utils/session.py`.
- `backend/app/data_access/excel_loader.py:52,67` + `excel_profiler.py:55` + `notebook/routes.py:78,136` -- perfilar cada hoja (`pd.ExcelFile`), endpoint/paso para elegir hojas, apilar con columna `Hoja` y columnas comunes.
- `backend/app/notebook/chart_builder.py:76-83` + `frontend/src/app/shared/money-format.ts:12-32` -- coincidencia por palabra/token (split por espacios/_/-) en vez de subcadena; mantener "N E T O".
- `backend/app/notebook/table_builder.py:153-195,275,332,371` -- `_pareto_marker_lines`/`build_summary_code`/`build_summary_detail_code`: kwargs `agg='sum'|'mean'|'count'`, `top_n=None`, `negatives` según decisión; "(vacío)" separado. Callers: `routes.py:464,466`, `analysis_catalog.py:113`, tests.
- `backend/app/notebook/analysis_catalog.py:77-131` -- usar `agg` por métrica, Top N en vez de omitir >15, bloque de tendencia mensual por cada `fecha` × métrica principal, devolver `codigo` en cada bloque, aceptar `filters` (reusa `table_builder._filter_lines`); `routes.py:548-590` valida y pasa filtros/agregaciones.
- `backend/app/notebook/semantic_classifier.py:38-44,130-143` -- payload según decisión de consentimiento.
- `backend/app/data_access/excel_profiler.py:370-388` -- ya emite `nullRatio`/`uniqueRatio`; agregar duplicados, negativos por columna numérica y filas de totales removidas al profile.
- `backend/app/guided/challenges.py:53,90,111,138,151` + `content.py` + `data_context.py:24` -- retos nuevos para 00/02/04/05 y 06/07/08; checkers reciben `pristine` y comparan contra él; `CHALLENGE_TO_LESSON` derivado de `LESSONS`. Cada tabla sintética de lección tiene un constructor canónico en el servidor (mismo código que el paso de la lección) y su copia de referencia se genera desde ahí, no desde el namespace del alumno.
- `frontend/src/app/shared/analysis-block/*`, `analysis-dashboard/*` -- botón "Ver el código"; `@Output` de selección → filtro cruzado en el dashboard (chip "Filtrado por X = Y · quitar"); tarjeta de tendencia (línea Chart.js en `chart-canvas` vista nueva `'tendencia'`).
- `frontend/src/app/shared/column-classification/*` -- selector de agregación por métrica (Suma por defecto; Promedio sugerido si el nombre tiene precio/tarifa/tasa/%/porcentaje/promedio).
- `frontend/src/app/no-code/no-code-home/*` -- panel "Calidad de tus datos" entre pasos 1 y 2; selector de hoja si aplica.
- `frontend/src/app/notebook/notebook-home/notebook-home.component.ts:55-60,142` + `core/notebook-draft.service.ts` -- `appendCells()` y lectura al iniciar para abrir con el código del bloque.
- `frontend/src/app/core/session.service.ts` + `session.interceptor.ts` -- guardar el id firmado que devuelve el servidor y la clave de acceso si aplica.
- `frontend/src/app/no-code/.../no-code-table.component.ts:223,254` + `.html:181-195` -- narrativa según decisión de consentimiento.
- NO tocar: `backend/app/convatec/*`, `frontend/src/app/convatec/*`.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/notebook/worker.py`, `execution.py` -- entorno limpio, allowlist de imports, builtins reducidos, copia prístina -- riesgo #1 y anti-trampa.
- [x] `backend/app/notebook/worker_manager.py`, `app/__init__.py`, `config.py`, `app/utils/session.py` + 3 `routes.py` -- tope de sesiones, 413/503, sesión firmada, control de acceso, tope global IA.
- [x] `backend/app/data_access/excel_loader.py`, `notebook/routes.py` (upload) -- hojas múltiples.
- [x] `backend/app/notebook/chart_builder.py` + `frontend/src/app/shared/money-format.ts` -- dinero por palabra.
- [x] `backend/app/notebook/table_builder.py` -- `agg`, `top_n`, negativos, "(vacío)" aparte.
- [x] `backend/app/notebook/analysis_catalog.py`, `routes.py` (auto-analysis) -- agregaciones, Top N, tendencia, `codigo`, filtros.
- [x] `backend/app/data_access/excel_profiler.py` -- métricas de calidad.
- [x] `backend/app/notebook/semantic_classifier.py`, `no-code-table.*` -- consentimiento IA.
- [x] `backend/app/guided/{content,challenges,data_context}.py` -- retos 00-05, lecciones 06 limpieza / 07 fechas / 08 razonamiento con reto cada una.
- [x] `frontend` tablero, clasificación, no-code-home, notebook, sesión -- UI de todo lo anterior.
- [x] `backend/tests/*`, `frontend/**/*.spec.ts` -- casos de la matriz I/O y cada bug.

**Acceptance Criteria:**
- Given una lección cualquiera de 00 a 08, when el alumno solo ejecuta los pasos de ejemplo, then la lección no se marca completa hasta pasar su reto.
- Given una tarjeta del tablero, when se pulsa "Ver el código", then el Notebook abre con ese código en una celda nueva y al ejecutarlo da la misma tabla.
- Given el tablero generado, when se hace clic en una categoría, then todas las tarjetas se recalculan filtradas y un chip permite quitar el filtro.
- Given un archivo subido, when termina la carga, then el panel de calidad muestra vacíos, duplicados, negativos y filas de totales removidas.

## Implementation Notes

- Sesión firmada: `app/utils/session.py` (before/after_request). Todo `/api/*` sin token válido recibe uno nuevo en el header de respuesta `X-Session-Id`; CORS lo expone. La clave de equipo protege todo `/api/*` salvo `/api/health` (superconjunto de execute/upload). `/api/health` informa `accessKeyRequired` y `maxUploadMb`.
- Tests: `conftest.py` instala un `FlaskClient` que reenvía el token emitido (los ids "session-a"/"session-b" de tests viejos funcionan como etiquetas).
- Anti-trampa: el worker guarda copia prístina de cada `bind` y, para tablas sintéticas de lecciones (`SNAPSHOT_TABLE_VARS`), la primera vez que aparecen tras un `exec`.
- Negativos/"(vacío)": comportamiento por defecto (`negatives="separate"`) en resumen agrupado manual y tablero; las líneas "Fuera del ranking:" van en stdout después de la frase 80/20 y el catálogo las separa en `fueraDelRanking`. La vista por filas (`build_sort_code`) no cambia.
- Hojas: `POST /api/notebook/select-sheets`; el libro pendiente se conserva para reseleccionar (quitar una hoja) hasta otra subida/reinicio/TTL.
- Tendencia: bloques extra (máx. 2) que no consumen `MAX_AUTO_BLOCKS`.

### Iteración 1 (2026-11-19)

- La reimplementación del backend se hizo con subagente; la sesión de Claude Code se cerró dos veces (presión de memoria del sistema), así que el frontend y los tests de frontend se completaron en línea en la sesión principal, sobre el mismo árbol.
- Secretos: `app/utils/secrets.py` los captura en `create_app()` y los saca de `os.environ` antes de crear workers; `config.py` ya no tiene atributos secretos; E/S de archivos/URL/pickle de pandas/numpy/matplotlib bloqueada en el worker (buffers en memoria permitidos).
- Copia de referencia de tablas sintéticas: se construye con el código canónico de la lección, no desde el namespace del alumno.
- Filtro cruzado: al tocar una categoría se selecciona (detalle en la tarjeta) y el botón «Filtrar todo el tablero por esta categoría» re-ejecuta el catálogo con el filtro. Se eligió el paso explícito para que un clic de exploración no dispare un recálculo de ~30 s de todo el tablero; el chip «Filtrado por X = Y · quitar» lo revierte. Las filas «Otros (k)» y los meses de tendencia no son filtrables.
- Tendencia: vista `tendencia` (línea) en `chart-canvas`; las tarjetas de tendencia solo ofrecen Línea/Tabla y sin % del total.
- Top N: si el backend ya plegó a `topN` + «Otros», la tarjeta no aplica además su Top 10 por defecto; nota «Se muestran las N principales de M».
- Clave de equipo: pantalla en `App`; la clave solo se acepta con respuesta exitosa de un endpoint protegido (`/api/guided/lessons`); 401 → «no es correcta», otro error → «no se pudo verificar», en ambos casos se borra.
- "Ver el código": `NotebookDraftService.enqueue/takeQueue` (localStorage con respaldo en memoria) y el Notebook las agrega como celdas nuevas al iniciar, sin reemplazar el borrador.
- Agregación por métrica: selector en la clasificación (Sumar/Promediar/Contar filas), sugerido Promediar para precio/tarifa/tasa/%/margen; viaja como `agg` en cada clasificación.

## Spec Change Log

### Iteración 1 (2026-11-19) — loopback por bad_spec

- **Hallazgos que lo dispararon:** triage #1-#4 (grupo A: secretos legibles por `/proc/*/environ`, secretos en `Config` al importar, E/S de pandas/numpy sin filtrar, `urllib.request` alcanzable) y #6 (grupo B: copia de referencia de tablas sintéticas tomada del namespace del alumno).
- **Qué se enmendó:** Code Map (worker, worker_manager, config/`__init__`, lectores de secretos, execution, challenges) y Design Notes (Secretos, E/S, Copia de referencia).
- **Estado malo que se evita:** creer cerrada la fuga de `GEMINI_API_KEY`/`SECRET_KEY` cuando sigue legible con `pd.read_csv('/proc/self/environ')`; retos pasables creando la tabla de ejemplo antes del paso de la lección.
- **Estados malos adicionales a evitar (hallazgos patch de la pasada 1; el código se revirtió):** filtro cruzado con dimensiones numéricas compara valores normalizados (float `3.0` == etiqueta `3`); cardinalidad y Top N se calculan sobre los datos filtrados; "(vacío)" se detecta por igualdad exacta de la clave, no subcadena; una tarjeta con `topN` del backend no aplica además el Top 10 del frontend y el texto usa el `TOP_N` real; la tendencia maneja fechas numéricas fraccionarias y seriales de Excel (origen 1899-12-30) sin error y rellena meses vacíos; `stack_sheets` devuelve `header_row_index=None`; `select-sheets` deduplica y rechaza nombres inexistentes; la lección 08 incluye un cliente con neto ≤ 0; el clasificador envía solo `name` y `type`; `SessionService` tiene respaldo en memoria si localStorage falla; las peticiones iniciales esperan el primer token (no crean sesiones paralelas); `submitAccessKey` acepta la clave solo con respuesta exitosa. Tests requeridos además de la matriz: 05-graficas por ruta/manager (pasa con gráfica, falla sin ella), `/summary-table` con `agg` válido e inválido, narrativa con `consent:true` (200, LLM simulado), reinicio diario del tope global, clave incorrecta/correcta en `app.spec.ts`, lectura de `/proc/self/environ` y `read_pickle` desde una celda bloqueadas, tabla sintética creada por el alumno antes del paso no permite pasar el reto.
- **KEEP (funcionó bien, debe sobrevivir):** sesión firmada con `itsdangerous` en `app/utils/session.py` (before/after_request, header expuesto por CORS, sin "anonymous"); clave `X-Access-Key` en todo `/api/*` salvo `/api/health`, que informa `accessKeyRequired`/`maxUploadMb`; `CapacityError` → 503 y 413 vía `api_response`; tope global diario de IA; `__import__` filtrado por frame `<celda>` y builtins reducidos como copia (sin mutar `builtins`); dinero por tokens (separadores, camelCase, plurales; "N E T O"; "cantidad" anula) en Python y TS; `table_builder` con kwargs `agg`/`top_n`/`negatives='separate'` y líneas "Fuera del ranking:" después de la frase 80/20; catálogo con `codigo` (cabecera de comentario aplanada contra saltos de línea), Top 15 + "Otros (k)", tendencia (máx. 2, sin consumir `MAX_AUTO_BLOCKS`), `filters`; `POST /select-sheets` apilando con `Hoja`; panel de calidad; diálogo de consentimiento con filas/grupos/columnas; `conftest.py` con cliente que reenvía el token; lecciones 06/07/08 y reto en 00-08 con solución de referencia probada.

## Review Triage Log

### Pasada 1 (2026-11-19)

| # | Hallazgo (capa) | Veredicto | Evidencia | Ruta |
|---|---|---|---|---|
| 1 | Secretos legibles vía `/proc/self/environ` y `/proc/<ppid>/environ` con lectores de pandas (blind, edge) | high | `os.environ.pop` en el hijo no reescribe el bloque inicial del kernel; `pd.read_csv` acepta rutas y no está filtrado. | bad_spec (grupo A) |
| 2 | `Config.SECRET_KEY`/`APP_ACCESS_KEY` cargados en memoria del worker antes del scrub (edge) | high | El hijo spawn importa el paquete `app` (config.py:21,24 evalúa os.environ al importar) antes de `worker_loop`. | bad_spec (grupo A) |
| 3 | E/S de archivos/red/pickle por pandas/numpy sin filtrar (blind, edge) | high | `read_csv/read_pickle/to_csv/np.fromfile` aceptan rutas/URL; solo se filtran `import` y `open`. | bad_spec (grupo A) |
| 4 | `import urllib.parse` liga el paquete `urllib`; `urllib.request` alcanzable (edge) | medium | pandas ya importa urllib.request, queda en el atributo del paquete. | bad_spec (grupo A) |
| 5 | `pd.__builtins__` expone builtins reales (edge) | low | Escape conocido; la spec lo acepta como "atacante decidido". | rechazado: aceptado por el modelo de amenaza documentado |
| 6 | Snapshot "prístino" de tablas sintéticas toma la primera versión vista, trampeable (blind, edge x2) | medium | `_snapshot_new_tables` copia lo que haya en el namespace; el alumno puede crearla antes. | bad_spec (grupo B) |
| 7 | Peticiones paralelas iniciales crean sesiones distintas (blind, edge) | medium | Sin token guardado cada petición recibe uno nuevo; gana la última respuesta. | patch |
| 8 | `submitAccessKey` acepta la clave ante errores no-401 (blind) | medium | app.ts acepta en red caída/5xx/503. | patch |
| 9 | Producción puede quedar sin clave en silencio (blind) | low | Es el comportamiento pedido si la variable no existe; solo falta aviso. | rechazado: decisión #1 lo permite; aviso no requerido |
| 10 | Tokens de sesión sin expiración (blind) | low | `Signer` sin max_age; con clave de equipo el riesgo es bajo. | rechazado: improbable en uso diario |
| 11 | Un cliente puede llenar los 8 cupos (blind) | low | Matriz define 503 al llenarse; con clave de equipo solo el equipo accede. | rechazado: improbable con 2-3 usuarios |
| 12 | Doble memoria por copia prístina (blind) | low | Acotado por `MAX_UPLOAD_MB`=15. | rechazado: improbable |
| 13 | Tendencia falla con fechas numéricas fraccionarias o seriales de Excel (blind, edge) | medium | `astype('Int64')` lanza TypeError; serial 45000 se lee como YYYYMMDD -> NaT. | patch |
| 14 | Tendencia compara meses no consecutivos y no marca mes parcial (blind) | medium | `_serie` sin meses vacíos rellenados. | patch |
| 15 | Filtro cruzado usa cardinalidad sin filtrar (blind, verif) | medium | `_usable_dimensions` corre sobre `variable` sin `_filter_lines`. | patch |
| 16 | Top N doble (backend 15, tarjeta 10) y texto "15" fijo (blind) | low | analysis-block aplica `topN=10` también a tarjetas ya plegadas; Otros queda oculto por defecto. | patch |
| 17 | Clic en categoría numérica vacía todas las tarjetas (blind) | high | Columna float por NaN: Python `astype(str)`="3.0", JS `String(3)`="3"; Matecol `Vdor` tiene "(vacío)" -> float. | patch |
| 18 | "(vacío)" detectado por subcadena (blind, edge) | low | `str.contains` saca combinaciones con un nivel vacío; corrección directa a igualdad. | patch |
| 19 | Lección 8: datos de ejemplo sin cliente con neto ≤ 0 (blind) | low | `df_ventas` no ejercita la regla que enseña; corrección directa de datos. | patch |
| 20 | Panel de calidad trunca a 50 columnas sin avisar (blind, edge) | low | Raro en la práctica y la corrección agrega un campo. | rechazado: improbable |
| 21 | `stack_sheets` reporta `header_row_index` sin sentido (blind) | low | Máximo entre hojas; corrección directa: `None`. | patch |
| 22 | `select-sheets` con duplicados o nombres inexistentes (blind, edge) | low | `["A","A"]` apila 1 hoja con columna `Hoja`; nombres desconocidos se ignoran. | patch |
| 23 | Detalle con `agg` mean/count calcula % sobre sumas (edge) | low | '% de su grupo' sigue siendo coherente como participación de fila. | rechazado: improbable/inocuo |
| 24 | Reembolso tras medianoche descuenta del día nuevo (edge) | low | Ventana de segundos. | rechazado: improbable |
| 25 | `MAX_UPLOAD_MB` ≤ 0 rechaza todo (edge) | low | Mala configuración. | rechazado: improbable |
| 26 | "Cambiar hojas" tras cargar otra tabla re-bindea el libro viejo (edge) | low | Flujo poco común. | rechazado: improbable |
| 27 | Clasificador envía `uniqueRatio` además de nombre y tipo (edge, claim) | low | La decisión #2 dice "solo nombres y tipos"; desviación directa, corrección = borrar el campo del payload. | patch |
| 28 | El servicio siempre manda `consent:true` (edge, claim) | false | La llamada solo ocurre tras confirmar el diálogo en no-code-table; no hay otro llamador. | rechazado |
| 29 | `had_chart` no probado de punta a punta (verif) | medium | Pre-verificado: sin test por manager/ruta para 05-graficas. | patch |
| 30 | `agg` en `/summary-table` sin test de ruta (verif) | medium | Pre-verificado. | patch |
| 31 | Consentimiento: solo se prueba el rechazo (verif) | medium | Pre-verificado. | patch |
| 32 | Reinicio diario del tope global sin test (verif) | medium | Pre-verificado. | patch |
| 33 | Clave incorrecta en `submitAccessKey` sin test (verif) | medium | Pre-verificado. | patch |
| 34 | `SessionService` sin respaldo en memoria si localStorage falla (verif) | medium | Cada petición sin token crea sesión nueva y llena cupos. | patch |
| 35 | Nombres compuestos en minúscula (`valortotal`) ya no son dinero (verif) | low | Cambio de comportamiento; encabezados reales suelen tener separador. | rechazado: improbable |
| 36 | Cardinalidad sin filtrar (verif, duplicado de #15) | medium | Misma causa que #15. | patch (con #15) |

### Pasada 2 (2026-11-19, iteración 1)

| # | Hallazgo (capa) | Veredicto | Evidencia | Ruta |
|---|---|---|---|---|
| 1 | `fueraDelRanking` llega como objetos `{grupo, valor, motivo}`; la tarjeta los pintaba como texto (edge, claim) | high | analysis_catalog.py:136 arma dicts; el template interpolaba el objeto -> `[object Object]`. | patch (corregido: tipo `OutOfRanking` y render) |
| 2 | Tarjetas de tendencia: registros con clave `Mes`, tarjeta buscaba la columna de fecha (edge, claim) | high | `_serie.index.name = 'Mes'` vs `"dimension": date_column`; todas las etiquetas caían a "(vacío)". | patch (corregido: `categoryKey` = `Mes` en tendencias) |
| 3 | Filtro que deja 0 tarjetas oculta el chip y no se puede quitar (edge, claim) | medium | `@if (bloques.length > 0)` envolvía todo el tablero. | patch (corregido) |
| 4 | `__builtins__['__import__']('os')` saltaba el filtro (blind, edge) | high | El guard solo filtraba opcode `IMPORT_NAME`; una llamada directa pasaba. | patch (corregido: denylist OS/red en llamadas directas desde celda; `strftime` sigue funcionando) |
| 5 | Alias de E/S sin guard: `pd.io.parsers.read_csv`, `pd.ExcelFile`, `np.memmap`, `plt.imread`, `scipy.io`, `sns.load_dataset` (blind, edge) | high | `install_io_guards` solo parchaba `pd.*`/`np.*` de nivel superior. | patch (corregido: `pandas.io.common.get_handle` en todos los módulos pandas + numpy/matplotlib/scipy/seaborn) |
| 6 | `run_dev.py` recarga `.env` en cada worker spawn (blind) | medium | `load_dotenv()` a nivel de módulo; spawn re-importa `__mp_main__`. | patch (corregido: solo dentro de `__main__`) |
| 7 | Interceptor: si la primera petición falla, las que esperaban salen todas sin token (blind) | medium | `switchMap(() => this.send(...))` no re-evaluaba el estado. | patch (corregido: re-entra a `intercept`) |
| 8 | Consentimiento: al confirmar se recalculaban los datos en vez de enviar lo mostrado (edge) | medium | `generateNarrative` llamaba de nuevo `buildNarrativeStats()`. | patch (corregido: se envía exactamente lo aprobado) |
| 9 | Fechas numéricas YYYYMM/año leídas como seriales de Excel (edge) | medium | Solo distinguía YYYYMMDD vs serial. | patch (corregido) |
| 10 | Datos mensuales fechados el día 1 marcados como mes incompleto (edge) | medium | `_parcial = día < días_del_mes` siempre cierto. | patch (corregido: solo si hay días variados) |
| 11 | Dinero pegado a puntuación/dígitos (`Valor($)`, `Neto:`, `Venta2026`) no detectado (edge) | low | Separadores solo espacios/_/-/./`/`; corrección directa en Python y TS. | patch (corregido) |
| 12 | Sin test: hoja inutilizable primero + hoja usable (verif) | medium | Pre-verificado. | patch (test agregado) |
| 13 | Sin test: conteos de filas de totales/vacías en calidad (verif) | medium | Pre-verificado. | patch (test agregado) |
| 14 | Sin test: columnas excluidas salen de `quality` al confirmar limpieza (verif) | medium | Pre-verificado. | patch (test agregado) |
| 15 | Sin spec: diálogo de consentimiento del frontend (verif) | medium | Pre-verificado. | patch (spec agregado) |
| 16 | Sin spec: selector de hojas del frontend (verif) | medium | Pre-verificado. | patch (spec agregado) |
| 17 | Tokens de sesión sin expiración (blind, edge) | low | carried: pasada 1 #10. | rechazado |
| 18 | Un cliente llena los cupos; sin mensaje 503 específico (blind) | low | carried: pasada 1 #11; las pantallas muestran el mensaje del backend. | rechazado |
| 19 | Producción abierta si falta `APP_ACCESS_KEY` (blind) | low | carried: pasada 1 #9 (decisión #1). | rechazado |
| 20 | Clave de equipo en localStorage sin expiración (blind) | low | Herramienta interna de 2-3 personas; mitigarlo agrega un flujo de intercambio de tokens. | rechazado: improbable |
| 21 | Filtro sobre texto "3.0" normalizado a "3" (blind, edge) | low | Categorías de texto con forma de float entero son raras. | rechazado: improbable |
| 22 | `agg='mean'`: % del total y 80/20 sobre suma de promedios (blind) | medium | La matriz congelada define "Pareto sobre la media por grupo"; cambiarlo es decisión de intención. | defer (intención; ver deferred-work) |
| 23 | Memoria: copia prístina + libros pendientes sin tope (blind, edge, verif) | low | Acotado por `MAX_UPLOAD_MB`; el worker no tiene `RLIMIT_AS`. | rechazado: improbable |
| 24 | Tope diario de IA en memoria y por UTC (blind) | low | Se reinicia con el proceso; el tope por sesión sigue. | rechazado: improbable |
| 25 | Ajustes numéricos ≤ 0 (blind, edge) | low | carried: pasada 1 #25. | rechazado |
| 26 | Consentimiento solo como bandera del cliente (blind) | low | carried: pasada 1 #28; el único llamador es el diálogo. | rechazado |
| 27 | Token viejo + peticiones paralelas abren sesiones distintas (edge) | low | Solo al rotar `SECRET_KEY`. | rechazado: improbable |
| 28 | Etiqueta fuera del ranking con salto de línea se pierde (edge) | low | Celdas multilínea en categorías son raras. | rechazado: improbable |
| 29 | Retos: NaN en `mov_neto` / índice no verificado en `ventas_por_mes` (edge) | low | Datos de lección sintéticos sin NaN; anti-trampa por valores. | rechazado: improbable |
| 30 | Colisión `Hoja` + `Hoja_origen` (edge) | low | Doble colisión de nombres improbable. | rechazado: improbable |
| 31 | Reembolso de cupo IA tras medianoche (edge, verif) | low | carried: pasada 1 #24. | rechazado |
| 32 | `convatec/routes.py` sigue con `"anonymous"` (verif) | low | Blueprint desconectado; preexistente y fuera del alcance (no tocar Convatec). | defer |

## Design Notes

El filtro de imports actúa solo sobre imports cuyo frame llamador es `<celda>`; así pandas/matplotlib siguen importando `os` internamente. Ejemplo:

```python
def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    caller = sys._getframe(1).f_code.co_filename
    if caller == "<celda>" and name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"El import de '{name}' no está permitido en este entorno.")
    return _real_import(name, globals, locals, fromlist, level)
```

La copia prístina vive en el worker (mismo proceso que el alumno): es privada por convención, suficiente para el modelo de amenaza "accidentes/abuso casual".

**Secretos.** Borrar `os.environ` en el hijo no basta: en Linux `/proc/self/environ` conserva el bloque inicial del proceso y `/proc/<ppid>/environ` el del padre (mismo usuario). Por eso: (1) `create_app()` captura los secretos en `app.config` y los ELIMINA de `os.environ` del padre antes de crear cualquier worker, así los hijos spawn nacen sin ellos; (2) ningún módulo del paquete `app` evalúa secretos al importarse; (3) el bloqueo de E/S (abajo) impide leer `/proc/*` desde una celda. Lo que queda (p. ej. `pd.__builtins__`) es "atacante decidido", aceptado y documentado en `worker.py`.

**E/S.** En el worker, antes de ejecutar celdas, envolver los lectores/escritores con ruta de pandas (`read_*`, `DataFrame/Series.to_*` con destino ruta; `read_pickle`/`to_pickle` siempre bloqueados), numpy (`load`, `save`, `savez`, `fromfile`, `tofile`, `loadtxt`, `genfromtxt`) y `Figure.savefig`/`plt.savefig`: si el destino/origen es `str`/`PathLike`/URL → `PermissionError("Leer o escribir archivos no está permitido en este entorno.")`; objetos en memoria (BytesIO/StringIO) siguen permitidos (los usa `_capture_figure`). El código generado por el backend no lee archivos (los datos llegan por `bind`).

**Copia de referencia de tablas sintéticas.** Para `df_02_movimiento`, `df_02_item`, `df_clientes`, `df_ventas`: el checker construye la tabla de referencia ejecutando el código canónico del paso de la lección (fuente: `content.py`) en un namespace aparte del worker, cacheado por sesión; nunca toma la versión del namespace del alumno.

## Verification

**Commands:**
- `cd backend && venv/Scripts/python.exe -m pytest -q` -- expected: todo pasa, incluidos tests nuevos de la matriz.
- `cd frontend && npx ng test --watch=false --browsers=ChromeHeadless` -- expected: 0 fallos.
- `cd frontend && npx ng build` -- expected: compila sin errores.

**Manual checks (if no CLI):**
- En Chrome (extensión): subir `relacion de facturas matecol.xlsx`, revisar panel de calidad, tablero con Top N, tendencia, filtro cruzado, "Ver el código"; Notebook con `import os` bloqueado; un reto trampeado no pasa.
