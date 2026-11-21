---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
status: 'complete'
completedAt: '2026-07-12'
inputDocuments: ['prd-sico-pandas-lab-2026-07-12.md']
workflowType: 'architecture'
project_name: 'sico-pandas-lab'
repoPath: 'REPOSITORIOS/sico-pandas-lab (pendiente de crear, repo standalone, no adjunto a SICO hasta aprobación del dueño)'
user_name: 'Maximun_neo'
date: '2026-07-12'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

22 FRs organizados en 6 áreas de capacidad: Gestión de Usuarios y Acceso (3), Conexión a Fuentes de Datos (4), Notebook de Práctica Libre (6), Módulo de Aprendizaje Guiado (4), Seguridad y Aislamiento de Ejecución (3), Administración (2). El núcleo arquitectónico es un motor que ejecuta código Python/pandas escrito por el usuario y expone, dentro de ese código, un DataFrame ya cargado desde Excel o desde una consulta de solo-lectura a MariaDB.

**Non-Functional Requirements:**

- **Security** es la NFR que más pesa: solo-lectura real a nivel de motor de BD (no solo capa de app), sandboxing por sesión, credenciales nunca expuestas al código del usuario. Esto no es negociable dado que la fuente de datos es una base de producción real.
- **Performance**: expectativa suave (celdas responden en segundos), sin necesidad de optimización agresiva.
- **Reliability**: sin SLA formal, uso en horario laboral.
- **Scalability**: explícitamente NO es prioridad — solo 2-3 usuarios.
- **Integration**: conexión de red hacia una RDS existente (ubicación VPC/pública sin confirmar), y diseño de autenticación que no bloquee una futura integración SSO con sico-web.

**Scale & Complexity:**

- Primary domain: full-stack web app (frontend SPA + backend + motor de ejecución de código + acceso a datos)
- Complexity level: medium-high — no por volumen de usuarios (solo 2-3), sino por la necesidad de ejecutar código arbitrario de forma segura contra una base de datos de producción real
- Componentes arquitectónicos estimados: (1) Frontend SPA tipo notebook, (2) Backend API, (3) Motor de ejecución de código aislado (sandbox), (4) Capa de acceso a datos (RDS solo-lectura + parsing de Excel), (5) Gestión de usuarios/autenticación, (6) Contenido del módulo guiado

### Technical Constraints & Dependencies

- Debe conectarse en modo solo-lectura a la RDS MariaDB de producción existente (`<endpoint-de-la-rds-de-sico>`) — pendiente confirmar si el acceso de red es público restringido por IP o requiere VPC/VPN.
- Proyecto greenfield: no hay codebase existente que reutilizar, aunque se anticipa integración futura con sico-web (fuera de alcance del MVP).
- Base de usuarios pequeña y fija (2-3 personas) — la arquitectura debe priorizar simplicidad y seguridad sobre escalabilidad.
- ⚠️ Antes de construir un motor de ejecución/kernel custom desde cero, evaluar soluciones OSS existentes (ej. JupyterHub con kernels restringidos, o un servicio gestionado equivalente) que puedan adaptarse — no hay diferenciación de producto en reinventar esta pieza si algo probado ya resuelve el aislamiento.

### Cross-Cutting Concerns Identified

- **Aislamiento de ejecución de código (Decisión Arquitectónica #1 — bloqueante):** afecta el diseño del backend, la capa de datos y la gestión de sesiones por igual. Ninguna otra decisión técnica (lenguaje de backend, hosting, modelo de sesiones) debería fijarse antes de resolver esta.
- **Enforcement de solo-lectura redundante y verificable**: debe aplicarse tanto a nivel de permisos de MariaDB como en el diseño del motor de ejecución — y debe existir una prueba automatizada que intente una escritura y confirme el rechazo a nivel de motor, no solo revisión manual.
- **Gestión de credenciales y fuga vía entorno de proceso**: las credenciales de la RDS nunca deben llegar al entorno donde corre el código del usuario. Riesgo explícito: si el sandbox no aísla el proceso por completo, el código del usuario podría leer variables de entorno del sistema donde a veces se guardan credenciales por descuido — el aislamiento debe ser a nivel de proceso/contenedor, no solo de biblioteca.
- **Desacoplamiento de autenticación (sin sobre-diseñar)**: evitar el anti-patrón de lógica de auth dispersa por todo el código, para no bloquear la futura integración SSO con sico-web — pero sin construir ya un sistema de auth "pluggable" completo. Esa integración está fuera de alcance del MVP; resolver hoy solo lo mínimo para no cerrarse puertas.
- **Modelo de ejecución de celdas (síncrono vs. streaming)**: decisión pendiente entre respuesta simple request/response vs. streaming incremental de output (WebSocket/SSE), como en un notebook real. Recomendación mínima para el MVP: la arquitectura debe soportar al menos un estado "ejecutando…" visible por celda, incluso si el streaming completo de stdout se deja para después — una pantalla congelada durante una consulta de varios segundos rompe la confianza de usuarios de nivel básico.

## Starter Template Evaluation

### Preferencias técnicas confirmadas

- **Backend:** Flask (Python), pensado desde ya como microservicio que después se alinea con los demás microservicios (Java) existentes en **ECR + ECS sobre EC2** ("ECS pelado con un puerto", sin balanceador complejo).
- **Frontend:** Angular, mismo major que **sico-web** (Angular 20.2.x + Angular Material), usando **NgModules** (módulos por feature, lazy-loaded) para replicar el patrón exacto de sico-web y facilitar una eventual fusión de código.
- **Contenedores:** Docker, siguiendo el mismo patrón de despliegue que los microservicios Java existentes.
- **Acceso a datos confirmado:** conexión directa de solo-lectura a la RDS MariaDB, esquema `sco`, limitada a las tablas `02_movcabeza`, `02_movimiento`, `02_item`, `02_itemprecios` — permite otorgar permisos `SELECT` acotados a estas 4 tablas específicas en vez de todo el esquema, reduciendo la superficie de exposición.
- **Autenticación del MVP:** login simple propio de la app (no se replica el flujo OIDC compartido de sico-web todavía) — hallazgo del código de sico-web: usa OAuth2/OIDC (`access_token`/`id_token`, endpoint `connect/logout`) más una API centralizada de permisos (`{userApiUrl}/sco/app/allowed?path=`). Se documenta como referencia para cuando llegue la integración real (fuera de alcance del MVP).

### Starter Options Considered

**Backend — Flask:**
Flask 3.1.3 es la versión estable actual (release de 2026-02-19, Python ≥3.9 requerido). Patrón de referencia: application factory (`create_app`), organización por Blueprints, configuración 12-factor vía variables de entorno, y en producción corre con Gunicorn detrás de un proxy — encaja directamente con el patrón "contenedor con un puerto expuesto" que ya usan en ECS.

**Frontend — Angular:**
Angular 20 trae *standalone components* por defecto en `ng new`, pero para este proyecto se descarta esa opción en favor de replicar el patrón NgModule de sico-web (decisión explícita del usuario, prioriza consistencia de integración futura sobre el default moderno del CLI). ⚠️ A verificar en la historia de inicialización: si `ng new --standalone=false` sigue disponible en Angular 20.2, o si se requiere configuración manual post-generación para forzar módulos.

**Motor de ejecución de código (sandboxing):**
No es un "starter" tradicional sino una decisión de arquitectura crítica (ver Decisión #1 en Cross-Cutting Concerns). La investigación confirma que el sandboxing de Python es intrínsecamente difícil (el sistema de objetos de Python permite escapar de restricciones ingenuas tipo `exec()` con globals limitados). Opciones reales usadas en producción por otros: contenedores con gVisor, AppArmor (ej. CodeJail de Open edX), o kernels de Jupyter aislados por contenedor. Dado el alcance del MVP ("algo más simple", 2-3 usuarios, sin fecha límite fija), la recomendación es un punto medio pragmático — ver sección siguiente.

### Selected Approach

**Backend:** Flask 3.1.3 con patrón *application factory* + Blueprints, servido con Gunicorn en el contenedor Docker (mismo patrón que los microservicios Java: un contenedor, un puerto, corriendo en ECS/EC2).

**Frontend:** Angular 20.2.x + Angular Material, estructurado con NgModules por feature (calcado de sico-web), gestionado con `yarn`.

**Acceso a datos:** conexión de solo-lectura vía SQLAlchemy/PyMySQL a MariaDB, con un usuario de base de datos cuyo `GRANT` se limita a `SELECT` sobre `sco.02_movcabeza`, `sco.02_movimiento`, `sco.02_item`, `sco.02_itemprecios` únicamente.

**Motor de ejecución (MVP):** un **proceso worker Python persistente por sesión** (no un subprocess nuevo por celda, para evitar el costo de arranque de intérprete en cada ejecución), que recibe código por IPC (pipe/queue), lo ejecuta y devuelve el resultado; se termina tras inactividad. Límites de CPU/memoria vía `resource.setrlimit` (Linux, coherente con contenedores en ECS), sin acceso al sistema de archivos fuera de un directorio temporal, y sin acceso de red saliente salvo hacia la RDS a través de la conexión ya autenticada que la app le inyecta.

⚠️ **Modelo de amenaza explícito:** este mecanismo protege contra **accidentes** de usuarios internos confiables (bugs, código que se cuelga, consumo descontrolado de memoria) — **no es un sandbox a prueba de un atacante malicioso decidido** (la investigación confirma que el sistema de objetos de Python permite burlar restricciones ingenuas). Si en el futuro el número de usuarios crece o cambia el nivel de confianza, se debe migrar a aislamiento por contenedor (gVisor/CodeJail) — documentado como upgrade natural en Growth, no necesario para el MVP.

**Excel:** lectura de archivos vía `pandas.read_excel` / `openpyxl` (nativo en Python, sin depender de librerías Node como `exceljs`).

**Editor de celdas de código:** evaluar **Monaco Editor** (el editor de VS Code) vía el paquete `ngx-monaco-editor-v2` (compatible con Angular 20, mantenido activamente) en vez de construir un editor de código desde cero — ahorra semanas de trabajo en resaltado de sintaxis, autocompletado básico y manejo de selección/cursor. ⚠️ Verificar en la historia de inicialización un issue reportado de comportamiento inestable del editor específicamente en Angular 20 antes de comprometerse a esta librería.

**Nota:** la inicialización de ambos proyectos (backend Flask, frontend Angular) debe ser la primera historia de implementación.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Acceso a la RDS: confirmado público con security group restringido por IP, solo-lectura. **Bloqueante real:** debe crearse un usuario de MariaDB dedicado a esta app con `GRANT SELECT` únicamente sobre `sco.02_movcabeza`, `sco.02_movimiento`, `sco.02_item`, `sco.02_itemprecios` — **no usar la cuenta `admin` compartida** que se mencionó en la conversación; esa cuenta tiene privilegios amplios y su uso rompería el enforcement de solo-lectura documentado en el PRD.
- ⚠️ A confirmar antes de implementar: si la conexión a la RDS debe forzarse por TLS (no se especificó explícitamente).
- Motor de ejecución: worker Python persistente por sesión, límites vía `resource.setrlimit` (ya definido en Starter Template Evaluation).

**Important Decisions (Shape Architecture):**
- Backend: Flask 3.1.3, patrón application factory + Blueprints, servido con Gunicorn.
- Frontend: Angular 20.2.x + Angular Material, NgModules (calcado de sico-web), editor de celdas con Monaco (`ngx-monaco-editor-v2`).
- Base de datos propia de la app (usuarios/roles/contenido guiado): SQLite + SQLAlchemy 2.0.51 ORM.
- Acceso a la RDS de sico: PyMySQL + `pandas.read_sql` con SQL parametrizado (sin ORM para estas consultas de solo-lectura).
- Autenticación MVP: Flask-Login 0.6.3 + sesión de servidor + hash de contraseña con `werkzeug.security`.
- Comunicación de ejecución de celdas: HTTP síncrono bloqueante (POST → resultado), sin streaming.
- Estado en frontend: servicios Angular + RxJS, sin NgRx.
- Despliegue: contenedor Docker en ECS sobre EC2, un puerto expuesto — mismo patrón que los microservicios Java existentes.

**Deferred Decisions (Post-MVP):**
- SSO/OIDC compartido con sico-web (existe un servidor de autorización y una BD `mappale_security` para esto, confirmados en la conversación, pero fuera de alcance del MVP).
- Streaming real de output de celdas (WebSocket/SSE).
- Aislamiento por contenedor (gVisor/CodeJail) si el número de usuarios o el nivel de confianza cambia.
- Pipeline de CI/CD específico — pendiente confirmar con el equipo si se replica el de los microservicios Java.
- Logging/monitoreo centralizado (CloudWatch u otro) — pendiente confirmar si los micros Java ya lo usan, para alinear el nuevo servicio.

### Data Architecture

- **Datos de sico (fuente fidedigna):** conexión de solo-lectura vía PyMySQL a MariaDB, acceso público con security group restringido por IP. Usuario de BD dedicado, `SELECT` limitado a `sco.02_movcabeza`, `sco.02_movimiento`, `sco.02_item`, `sco.02_itemprecios`. Sin ORM — las consultas van directo a DataFrames de pandas vía `pd.read_sql`, ya que el caso de uso es lectura/reporte, no CRUD.
- **Consultas combinadas (joins):** `data_access/sico_client.py` debe soportar SQL parametrizado con `JOIN` entre 2, 3 o las 4 tablas autorizadas de `sco` (no solo `SELECT` de una tabla individual) — requisito explícito del usuario, ya que el flujo real de análisis cruza `02_movcabeza`/`02_movimiento` con `02_item`/`02_itemprecios`.

**Relaciones reales del esquema `sco` (confirmadas por DDL del usuario):**

```
sco.02_movcabeza (indice PK auto_increment, cia)
        │  indice = mov_indice  AND  cia = mov_cia
        ▼
sco.02_movimiento (PK: mov_indice, mov_cia, mov_linea)
        │  mov_item = item_codigo  AND  mov_cia = item_cia
        ▼
sco.02_item (PK: item_cia, item_codigo)
        │  item_cia = cia  AND  item_codigo = codigo_item
        ▼
sco.02_itemprecios (PK: cia, codigo_item, tipo_campo_adicional)  ⚠️ tabla EAV: una fila por atributo/precio (tipo_campo_adicional identifica cuál, valor es el dato) — un mismo item tiene múltiples filas, no una sola
```

⚠️ Todas las columnas `cia`/`mov_cia`/`item_cia` deben incluirse en cualquier JOIN (esquema multi-compañía) — omitirlas produce combinaciones cruzadas incorrectas entre compañías distintas.
- **⚠️ Revisión de implementación — conexión directa (sin usuario de solo-lectura):** no existe un usuario de MariaDB de solo-lectura y no se creará por ahora; la app se conecta directo con las credenciales existentes (como DBeaver). La protección contra escrituras pasa a apoyarse en tres controles en el código, no en el grant del motor: (1) el código del usuario nunca toca la conexión —solo recibe DataFrames—; (2) `sico_client` solo construye `SELECT` sobre la allowlist de 4 tablas, con una barrera dura `assert_select_only()` que rechaza cualquier sentencia que no empiece por SELECT (y sentencias encadenadas), cubierta por pruebas; (3) cada conexión se pone en `SET SESSION TRANSACTION READ ONLY` mediante un listener de conexión de SQLAlchemy, así MariaDB rechaza toda escritura en la sesión aunque la cuenta pueda escribir. El health-check de arranque (FR21) se convierte en opt-in explícito (`SICO_ALLOW_WRITE_USER=true`): con cuenta privilegiada arranca en modo "degradado" con advertencia; sin el flag y con una cuenta que puede escribir, se niega a arrancar (evita el uso accidental). **Riesgo residual aceptado:** se pierde la barrera a nivel de motor; si en el futuro se crea un usuario de solo-lectura, se quita el flag y la protección vuelve a ser a nivel de motor.
- **⚠️ Cambio de alcance (revisión posterior a validación):** el MVP inicial **no incluye autenticación** — acceso abierto a quien tenga la URL, para desplegar rápido y mostrarle algo funcional al dueño. Login (Flask-Login + SQLite) queda como Growth, junto con la gestión de usuarios (FR1/FR2 originales). La BD propia SQLite deja de ser necesaria para el MVP inicial mientras no haya login ni contenido guiado persistente que lo requiera.
- **Datos propios de la app** (usuarios, roles Super Admin/Usuario, contenido del módulo guiado): SQLite gestionado con SQLAlchemy 2.0.51 ORM. No se justifica una instancia de BD separada en RDS para 2-3 usuarios; si el proyecto crece (más usuarios, integración con sico-web), esta pieza es la que se migraría primero a una BD gestionada.
- **Migraciones:** solo aplican a la BD propia (SQLite) — usar Alembic si el esquema de usuarios/contenido evoluciona; no aplica a los datos de sico (son de solo lectura, no los modelamos nosotros).
- **Caching:** no se requiere para el MVP dado el volumen de uso (2-3 usuarios).
- **Concurrencia en SQLite:** activar explícitamente `PRAGMA journal_mode=WAL` al inicializar la BD propia — evita contención de escritura si Gunicorn corre con más de un worker. No viene así por defecto, hay que configurarlo.
- **Health-check de privilegios en el arranque:** al iniciar, el backend debe consultar `INFORMATION_SCHEMA.TABLE_PRIVILEGES` (o equivalente en MariaDB) para el usuario de BD configurado, y **rechazar arrancar** si detecta cualquier privilegio distinto de `SELECT` sobre las 4 tablas autorizadas. No depender de que un humano recuerde no usar la cuenta `admin` — verificarlo en código.

### Authentication & Security

- **⚠️ Autenticación MVP: NINGUNA (decisión revisada).** El primer release es de acceso abierto a quien tenga la URL — sin login. Riesgo aceptado explícitamente en el PRD (solo-lectura + URL no difundida ampliamente). Flask-Login 0.6.3 + sesión de servidor + `werkzeug.security` quedan diseñados y documentados aquí, pero se implementan en Growth, antes de dar acceso oficial al equipo.
- **Autorización:** no aplica en el MVP sin login. El diseño de dos roles (Usuario, Super Admin vía campo `role`) queda para Growth.
- **Credenciales de la RDS:** gestionadas como variables de entorno inyectadas al contenedor (no hardcodeadas, no expuestas al código que ejecuta el usuario) — en producción, evaluar AWS Secrets Manager o SSM Parameter Store en vez de variables de entorno planas, dado que ya se maneja infraestructura AWS.
- **Aislamiento de ejecución:** ver "Motor de ejecución (MVP)" en Starter Template Evaluation — worker por sesión con límites de recursos, modelo de amenaza explícito (accidentes de usuarios internos confiables, no ataques).
- **TLS hacia la RDS:** ⚠️ pendiente de confirmar si debe forzarse.
- **Candidato a simplificar (revisar con PRD):** el panel de administración de usuarios (FR2, FR3, FR21 del PRD) podría no justificarse para 2-3 usuarios en el MVP — gestionar altas/bajas vía script/comando manual directo sobre la BD SQLite en vez de construir una UI de administración, dejando la UI como Growth si el uso real la justifica.

### API & Communication Patterns

- **Estilo de API:** REST simple entre el frontend Angular y el backend Flask (consistente con el patrón ya usado en sico-web vía `HttpClient`).
- **Ejecución de celdas:** un endpoint síncrono (`POST /notebook/execute`) que bloquea hasta obtener el resultado; el frontend muestra estado "ejecutando…" mientras espera. Sin colas ni WebSockets en el MVP.
- **Manejo de errores:** envelope JSON consistente para errores (código, mensaje claro, sin exponer detalles técnicos sensibles como cadenas de conexión), tal como exige la NFR de Reliability del PRD.
- **Rate limiting:** no se requiere para el MVP (2-3 usuarios internos conocidos).
- **Gráficas (FR12):** librería **matplotlib/seaborn** — alineada pedagógicamente con cómo se enseña pandas (`df.plot()` usa matplotlib por debajo), evitando introducir una herramienta distinta a la que el usuario encontrará en tutoriales y documentación estándar. Transporte: la figura generada en el worker se codifica como **PNG en base64** dentro de la respuesta JSON del endpoint de ejecución; el frontend Angular la renderiza directamente en un `<img>`, sin ninguna librería de charting del lado del cliente. Gráficas interactivas (Plotly/Bokeh) quedan como posible mejora de Growth, no del MVP.
  - **⚠️ Actualización 2026-09-22 (mesa redonda de interactividad/UX, ver `analisis-interactividad-ux-guiado-nocode-sico-pandas-lab-2026-09-21.md` y Épica 10 en `epics.md`):** esta mejora de Growth se concreta, específicamente para el tablero automático del **módulo sin código** (no para el notebook libre, que sigue como está descrito arriba), con **Chart.js** en vez de Plotly/Bokeh — Chart.js pesa ~60KB frente a ~1MB de Plotly sin tree-shaking, y `frontend/package.json` no tenía ninguna librería de gráficos instalada al momento de decidir. Esto implica que el backend sirva datos crudos (extendiendo `result_records` de `execution.py`) en vez de solo una imagen para esos bloques específicos del módulo sin código.

### Frontend Architecture

- **Módulos:** NgModules por feature (notebook de práctica libre, módulo guiado, administración), lazy-loaded — mismo patrón que sico-web.
- **Estado:** servicios Angular + RxJS; sin NgRx, no se justifica la complejidad adicional para este alcance.
- **Editor de código:** Monaco Editor vía `ngx-monaco-editor-v2` (compatible Angular 20) para las celdas — resaltado de sintaxis Python sin construir un editor propio.
- **Routing:** Angular Router estándar, con guards de autenticación simples (equivalente reducido a `auth.guard.ts` de sico-web, pero contra la sesión Flask-Login del MVP, no contra OIDC).

### Infrastructure & Deployment

- **⚠️ Hosting MVP (decisión revisada, reconfirmada tras evaluar AWS): Render.com**, no ECS/EC2 todavía — prioriza velocidad para tener una demo funcional que mostrarle al dueño antes de invertir en infraestructura AWS. Backend (`backend/`) y frontend (`frontend/`) se despliegan como dos Web Services separados en Render.
- **⚠️ Riesgo aceptado explícitamente:** usar Render requiere abrir el security group de la RDS a las IPs de salida de Render (o a internet público), y las credenciales de la RDS quedan almacenadas en un tercero (Render) fuera de la cuenta AWS de SICO. Se evaluó desplegar en la misma cuenta/VPC de AWS donde vive sico-web (tráfico interno, sin exposición pública, credenciales dentro de la cuenta ya controlada) — es la opción más segura, pero toma más tiempo de configuración. El usuario decidió mantener Render por velocidad para esta demo específica.
- **Camino de migración documentado (Growth):** cuando el dueño apruebe el proyecto, migrar a una **instancia EC2 nueva y standalone** (no mezclada con la infraestructura oficial de SICO) dentro de la misma cuenta/VPC — el usuario ya tiene acceso a la consola AWS pero no hay nada creado todavía para esto específicamente.
- **Portabilidad hacia ECS:** se mantienen los `Dockerfile` de cada subproyecto y se usa el modo de despliegue "Docker" de Render (no buildpacks nativos) — así el mismo artefacto migra a ECS/EC2 sin rehacer el empaquetado cuando se apruebe la integración formal con SICO (Growth).
- **Configuración:** 12-factor vía variables de entorno, tal como las expone Render (patrón recomendado por Flask 3.1 para producción).
- **CI/CD:** Render despliega automáticamente al hacer push a la rama configurada — suficiente para el MVP; el pipeline alineado con los microservicios Java (Jenkins/GitHub Actions/CodePipeline) queda para cuando se migre a ECS.
- **Logging/monitoreo:** logs de Render por ahora (logging estructurado a stdout); alinear con CloudWatch de los micros Java queda para la migración a ECS.

### Decision Impact Analysis

**Implementation Sequence:**
1. Conseguir/crear el usuario de MariaDB de solo-lectura acotado a las 4 tablas (bloqueante — no se puede implementar acceso a datos con la cuenta `admin`).
2. Inicializar los dos proyectos base: Flask (application factory) y Angular (NgModules) — primera historia de implementación.
3. Construir el motor de ejecución (worker persistente + límites de recursos) — es la pieza de mayor riesgo técnico, debe validarse temprano.
4. Capa de acceso a datos de solo-lectura (PyMySQL + pandas) contra las 4 tablas.
5. Autenticación simple (Flask-Login + SQLite) y los dos roles.
6. UI del notebook (Monaco Editor + ejecución síncrona) y del módulo guiado.
7. Despliegue en Docker/ECS siguiendo el patrón de los microservicios Java.

**Cross-Component Dependencies:**
- El motor de ejecución (paso 3) determina cómo se inyecta la conexión de datos de solo-lectura al código del usuario — no puede diseñarse la capa de datos en aislamiento de esta decisión.
- La autenticación simple del MVP (SQLite) es intencionalmente independiente del futuro SSO con `mappale_security`, para no bloquear el MVP ni sobre-diseñar una integración que aún no llega.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Hallazgo clave de sico-web:** ya existe un contrato de respuesta estándar usado por los microservicios Java (`ApiResponse<T> = { message, data, success, status }`, en `src/app/utils/api-response.utils.ts`). Este backend Flask adopta exactamente esa forma para minimizar fricción si sico-web llega a consumirlo directamente. Los DTOs existentes de sico-web mezclan `snake_case`/`camelCase` de forma inconsistente (legado) — no se replica esa inconsistencia; los campos nuevos de esta app usan `camelCase` limpio, solo el wrapper externo se calca exacto.

### Naming Patterns

**Backend (Python/Flask):**
- Funciones y variables: `snake_case` (PEP8).
- Blueprints por feature: `auth`, `notebook`, `data_access`, `admin`.

**Frontend (Angular):**
- Variables/funciones: `camelCase`. Clases/componentes: `PascalCase`. Archivos: `kebab-case` (igual que sico-web: `user-service`, `main-layout`).

**API:**
- Endpoints REST: sustantivos en plural, `kebab-case` si son multi-palabra — ej. `/api/users`, `/api/notebook/execute`.
- Campos JSON de respuesta: `camelCase` (el backend serializa de `snake_case` interno a `camelCase` en el borde de la API).

**Base de datos propia (SQLite):**
- Tablas en `snake_case` plural (ej. `users`). Foreign keys como `user_id`.

### Structure Patterns

**Backend:** patrón application factory (`create_app`), Blueprints por feature, `tests/` reflejando la estructura de `app/`.

**Frontend:** NgModules por feature bajo `src/app/<feature>/`, `*.spec.ts` co-ubicados junto a cada archivo — mismo patrón que sico-web.

### Format Patterns

**Wrapper de respuesta de API (calcado de sico-web):**
```json
{ "message": "string", "data": "T", "success": true, "status": 200 }
```

**Errores:** mismo wrapper, con `success: false` y `message` descriptivo, sin exponer detalles técnicos sensibles (cadenas de conexión, stack traces).

**Fechas:** ISO 8601 strings en JSON.

### Communication Patterns

**Estado de carga (frontend):** estado local del componente de la celda ("ejecutando…"), no un store global — consistente con la decisión de no usar NgRx.

### Process Patterns

**Manejo de errores:** los errores de ejecución de código del usuario se capturan y devuelven dentro del wrapper estándar (`success: false`), nunca como una excepción no controlada que resulte en un HTTP 500 genérico — esto es necesario porque los errores de código del usuario son un caso normal y esperado (Journey 2 del PRD), no una falla del sistema.

### Enforcement Guidelines

**Todos los agentes de IA que implementen este proyecto DEBEN:**
- Usar el wrapper `ApiResponse` en toda respuesta de la API Flask, sin excepción — a través de una **única función helper** (`api_response(data, message="", success=True, status=200)`), nunca construyendo el JSON de respuesta a mano en cada endpoint.
- Serializar `snake_case` (Python) → `camelCase` (JSON) en el borde de la API, nunca mezclar convenciones dentro de una misma respuesta.
- Seguir la estructura de Blueprints/NgModules por feature — no crear archivos sueltos fuera de esta organización.
- Nunca loguear ni devolver en un error la cadena de conexión a la RDS ni credenciales.

### Testing Patterns

- **Backend:** `pytest`.
- **Frontend:** `Jasmine/Karma` (default del Angular CLI, mismo framework que ya usa sico-web).
- **No negociable:** debe existir una prueba automatizada explícita que cubra el health-check de privilegios de solo-lectura (paso 4) — la verificación no puede quedar solo como diseño documentado sin test que la respalde.

## Project Structure & Boundaries

**Repositorio:** monorepo único `REPOSITORIOS/sico-pandas-lab/` con `backend/` y `frontend/` como subproyectos — no se divide en repos separados por servicio (a diferencia del patrón OR→BC de SICO) porque es una herramienta interna de 2-3 usuarios, no un módulo de negocio; dividir en repos añadiría fricción operativa sin beneficio real en este alcance.

### Complete Project Directory Structure

```
sico-pandas-lab/
├── README.md
├── docker-compose.yml              # orquesta backend + frontend en local para desarrollo
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example                # nunca .env real versionado
│   ├── wsgi.py                     # entrypoint para Gunicorn
│   ├── app/
│   │   ├── __init__.py             # create_app() — application factory
│   │   ├── config.py                # configuración 12-factor desde variables de entorno
│   │   ├── extensions.py            # init de extensiones (SQLAlchemy queda listo pero sin usar hasta Growth)
│   │   ├── startup_checks.py        # health-check de privilegios solo-lectura (Decisión #1, Paso 4) — sigue siendo no negociable aunque no haya login
│   │   ├── notebook/
│   │   │   ├── routes.py            # blueprint: POST /api/notebook/execute
│   │   │   ├── worker.py            # worker Python persistente por sesión (IPC + resource.setrlimit)
│   │   │   ├── worker_manager.py    # crea/reutiliza/mata workers por sesión — único responsable del ciclo de vida
│   │   │   └── charts.py            # figura matplotlib → PNG base64
│   │   ├── data_access/
│   │   │   ├── sico_client.py       # PyMySQL + pandas.read_sql, solo-lectura, incl. JOINs entre las 4 tablas de `sco`
│   │   │   └── excel_loader.py      # pandas.read_excel / openpyxl
│   │   ├── guided/
│   │   │   ├── routes.py            # blueprint: contenido del módulo guiado
│   │   │   └── content/             # lecciones/ejemplos (markdown o JSON)
│   │   └── utils/
│   │       └── api_response.py      # única función helper api_response(...)
│   └── tests/
│       ├── conftest.py
│       ├── test_startup_checks.py   # cubre el health-check de solo-lectura (no negociable)
│       ├── notebook/
│       └── data_access/
│
│   [Growth — no se construye en el MVP inicial, diseño ya documentado arriba en Authentication & Security:]
│   ├── app/auth/                    # routes.py, models.py (User sobre SQLite), decorators.py
│   ├── app/admin/cli.py             # gestión de usuarios vía Flask CLI (FR2 original)
│   ├── instance/app.db              # SQLite
│   └── migrations/                  # Alembic
└── frontend/
    ├── package.json
    ├── angular.json
    ├── tsconfig.json
    ├── Dockerfile
    ├── src/
    │   ├── environments/
    │   │   ├── environment.ts
    │   │   └── environment.development.ts
    │   └── app/
    │       ├── app.module.ts
    │       ├── app-routing.module.ts        # ⚠️ sin auth.guard.ts en el MVP — todas las rutas abiertas
    │       ├── notebook/                    # módulo de práctica libre
    │       │   ├── notebook.module.ts
    │       │   ├── notebook-routing.module.ts
    │       │   ├── components/
    │       │   │   ├── notebook-home/
    │       │   │   ├── data-source-panel/    # panel superior: conectar a esquema `sco` y elegir tabla(s), incl. combinaciones/joins
    │       │   │   ├── code-cell/            # Monaco Editor (ngx-monaco-editor-v2)
    │       │   │   └── cell-result/          # tabla / imagen base64 / error
    │       │   └── services/notebook.service.ts
    │       ├── guided/                       # módulo guiado
    │       │   ├── guided.module.ts
    │       │   ├── guided-routing.module.ts
    │       │   └── components/guided-lesson/
    │       ├── models/
    │       │   ├── api-response.ts           # espejo del wrapper del backend
    │       │   ├── cell-result.ts
    │       │   └── user.ts
    │       ├── services/data-source.service.ts   # abstrae Excel vs. RDS como fuente
    │       └── shared/
    │           ├── header/
    │           ├── main-layout/
    │           └── loading-overlay/
    └── tests/                        # Jasmine/Karma co-ubicados como *.spec.ts junto a cada archivo

[Growth — no se construye en el MVP inicial:]
frontend/src/app/auth/    # auth.module.ts, guards/auth.guard.ts, services/auth.service.ts
```

### Architectural Boundaries

**API Boundaries:** el frontend Angular solo habla con el backend Flask vía REST (`/api/*`); el backend es el único punto de contacto con la RDS de sico y con la BD propia (SQLite) — el frontend nunca accede a datos directamente.

**Component Boundaries:** `notebook/` (práctica libre) y `guided/` (módulo guiado) son módulos Angular independientes que comparten `services/data-source.service.ts` y los componentes de `shared/`; no se referencian directamente entre sí.

**Data Boundaries:** `data_access/sico_client.py` es el único módulo autorizado a abrir conexión hacia la RDS de sico — ningún otro módulo del backend debe importar un driver de BD directamente. `auth/models.py` es el único punto de acceso a la BD propia (SQLite).

### Requirements to Structure Mapping

- **FR1 (login), FR2 (gestión de usuarios vía script):** ⚠️ Growth — `backend/app/auth/` + `backend/app/admin/cli.py` (diseñados, no construidos en el MVP inicial).
- **FR4-FR7, FR6b (fuentes de datos + joins):** `backend/app/data_access/` + `frontend/.../data-source-panel/`.
- **FR8-FR13 (notebook libre):** `backend/app/notebook/` + `frontend/src/app/notebook/`.
- **FR14-FR17 (módulo guiado):** `backend/app/guided/` + `frontend/src/app/guided/`.
- **FR18-FR20 (seguridad/aislamiento):** `backend/app/notebook/worker.py` + `backend/app/startup_checks.py`.
- **FR21 (verificación automática de privilegios):** `backend/app/startup_checks.py` + `backend/tests/test_startup_checks.py`.

### Integration Points

**Comunicación interna:** HTTP síncrono REST entre `frontend/` y `backend/` (sin WebSockets en el MVP, según Paso 4). El ciclo de vida de los workers de ejecución (crear al abrir sesión, reutilizar entre celdas, matar por inactividad) es responsabilidad exclusiva de `notebook/worker_manager.py` — nunca se gestiona ad-hoc dentro de `routes.py`.

**Documentación del repo:** `README.md` apunta explícitamente a los documentos canónicos en `REPOSITORIOS/_bmad-output/` (`prd-sico-pandas-lab-2026-07-12.md` y `architecture-sico-pandas-lab-2026-07-12.md`) — no se duplica su contenido dentro del repo, siguiendo la misma regla de "no duplicar" que ya aplica en `SICO_CONTEXTO_MAESTRO.md`.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** Flask 3.1.3 + Angular 20.2.x + Docker/ECS son compatibles sin conflictos; todas las versiones fueron verificadas por web search en su momento. El patrón NgModules (decisión explícita del usuario) es compatible con Angular 20 aunque no sea el default del CLI — no genera conflicto técnico, solo requiere configuración manual verificable en la primera historia.

**Pattern Consistency:** Las convenciones de naming (snake_case backend / camelCase API-JSON / kebab-case archivos Angular) y el wrapper `ApiResponse` compartido son consistentes entre Paso 4 (Decisiones) y Paso 5 (Patrones) — no hay contradicciones.

**Structure Alignment:** El árbol del Paso 6 refleja fielmente los Blueprints/NgModules acordados en el Paso 5 (`auth`, `notebook`, `data_access`, `guided`, `admin`) y las piezas críticas del Paso 4 (`worker.py`, `worker_manager.py`, `startup_checks.py`, `api_response.py`).

### Requirements Coverage Validation

**Functional Requirements Coverage:** 21 de 22 FRs tienen soporte arquitectónico explícito (ver mapeo del Paso 6). **Gap encontrado:** FR22 (panel de actividad para Super Admin) — marcado como "⚠️ Supuesto a validar" desde el PRD — no tiene ninguna pieza arquitectónica asignada. Consistente con la simplificación ya aplicada a FR2/FR3/FR21, se recomienda **mover FR22 explícitamente a Growth** en el PRD en vez de dejarlo como MVP sin dueño arquitectónico.

**Non-Functional Requirements Coverage:** Security, Performance, Reliability y Scalability están cubiertas por decisiones concretas (solo-lectura verificable, worker aislado, WAL en SQLite, sin sobre-ingeniería de escalabilidad). Accessibility queda en nivel básico razonable (default de Angular Material), consistente con lo marcado como supuesto de bajo riesgo en el PRD.

### Implementation Readiness Validation

**Decision Completeness:** Todas las decisiones críticas e importantes están documentadas con versiones verificadas. **Dos decisiones quedan explícitamente abiertas** (ver Gap Analysis) y deben resolverse antes de implementar la capa de datos.

**Structure Completeness:** El árbol de directorios es completo y específico (no genérico) para ambos subproyectos.

**Pattern Completeness:** Naming, formato de API, manejo de errores y testing están definidos con ejemplos concretos.

### Gap Analysis Results

**Critical Gaps:** ninguno que bloquee el inicio de la implementación general — pero **sí bloquea específicamente la capa de acceso a datos**: falta crear el usuario de MariaDB de solo-lectura acotado a las 4 tablas (ya identificado en Paso 4, sigue pendiente).

**Important Gaps:**
- ⚠️ **TLS hacia la RDS:** sigue sin confirmarse si debe forzarse. Debe resolverse antes de implementar `data_access/sico_client.py`.
- ⚠️ **CI/CD y logging/monitoreo:** pendientes de confirmar con el equipo (patrón de los microservicios Java) — no bloquean el desarrollo inicial, pero sí el despliegue a producción.
- **FR22 sin dueño arquitectónico:** mover a Growth explícitamente en el PRD (ver arriba).

**Nice-to-Have Gaps:**
- Verificar el número de workers de Gunicorn en producción (1-2 recomendado inicialmente, dado SQLite+WAL y el bajo volumen de usuarios) — no está documentado como decisión explícita, solo implícito.
- Verificar en la historia de inicialización el issue conocido de Monaco Editor en Angular 20 (`ngx-monaco-editor-v2`) antes de comprometerse por completo a esa librería.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Contexto del proyecto analizado a fondo
- [x] Escala y complejidad evaluadas
- [x] Restricciones técnicas identificadas (RDS pública con SG restringido, ECS/EC2, integración futura con sico-web)
- [x] Preocupaciones transversales mapeadas

**✅ Architectural Decisions**
- [x] Decisiones críticas documentadas con versiones (Flask 3.1.3, Angular 20.2.x, SQLAlchemy 2.0.51, Flask-Login 0.6.3)
- [x] Stack tecnológico completamente especificado
- [x] Patrones de integración definidos
- [x] Consideraciones de performance abordadas

**✅ Implementation Patterns**
- [x] Convenciones de naming establecidas
- [x] Patrones de estructura definidos
- [x] Patrones de comunicación especificados (`ApiResponse`, HTTP síncrono)
- [x] Patrones de proceso documentados (manejo de errores, testing)

**✅ Project Structure**
- [x] Estructura completa de directorios definida
- [x] Límites de componentes establecidos
- [x] Puntos de integración mapeados
- [x] Mapeo de requisitos a estructura completo (21/22 FRs — FR22 pendiente de reclasificar)

### Architecture Readiness Assessment

**Overall Status:** LISTA PARA IMPLEMENTACIÓN, con 2 decisiones abiertas que deben cerrarse antes de tocar la capa de datos (TLS a la RDS, usuario de BD de solo-lectura).

**Confidence Level:** Alta — el proyecto es de alcance pequeño (2-3 usuarios), el stack está probado y alineado con el ecosistema SICO existente, y las decisiones de mayor riesgo (sandboxing, solo-lectura) tienen mitigaciones concretas y verificables por prueba automatizada.

**Key Strengths:** alineación deliberada con las convenciones reales de sico-web (contrato `ApiResponse`, Angular Material, NgModules); modelo de amenaza explícito en vez de sobre-prometer seguridad; alcance MVP deliberadamente recortado (sin UI de admin, sin streaming, sin SSO) para no gastar esfuerzo en lo que 2-3 usuarios no necesitan todavía.

**Areas for Future Enhancement:** streaming real de ejecución (WebSocket/SSE), aislamiento por contenedor si crece la confianza/usuarios, SSO compartido con `mappale_security`, gráficas interactivas (**Chart.js** para el módulo sin código — decidido 2026-09-22, ver Épica 10 en `epics.md`; ya no Plotly, ver actualización en API & Communication Patterns).

### Implementation Handoff

**AI Agent Guidelines:**
- Seguir todas las decisiones arquitectónicas exactamente como están documentadas en este archivo.
- Usar los patrones de implementación de forma consistente en todos los componentes.
- Respetar la estructura y los límites del proyecto definidos en el Paso 6.
- Consultar este documento para cualquier duda arquitectónica antes de improvisar.

**First Implementation Priority:** conseguir/crear el usuario de MariaDB de solo-lectura acotado a las 4 tablas de `sco`, y confirmar si se fuerza TLS — ambas cosas bloquean `data_access/sico_client.py`, que a su vez es dependencia de casi todo lo demás. En paralelo, inicializar los dos proyectos base (`backend/` con Flask application factory, `frontend/` con Angular NgModules) es la primera historia segura de arrancar sin depender de esas respuestas.

**Guía para Sprint Planning:** la autenticación, el scaffolding de ambos proyectos y el frontend del notebook (sin datos reales todavía) pueden desarrollarse en paralelo mientras se resuelven TLS y el usuario de solo-lectura — solo la épica de Acceso a Datos depende estrictamente de esas dos respuestas. No hay razón para bloquear el sprint completo por ellas.

**Integraciones externas:** RDS MariaDB (`data_access/sico_client.py`, solo-lectura); ninguna otra integración externa en el MVP (SSO/`mappale_security` queda fuera de alcance, documentado como Growth).

**Flujo de datos:** Excel subido o consulta a `sico_client.py` → DataFrame de pandas en el worker de ejecución → resultado (tabla/gráfica PNG base64/error) → `ApiResponse` → Angular renderiza en `cell-result/`.

### File Organization Patterns

- **Configuración:** `.env.example` en cada subproyecto (backend/frontend), nunca `.env` real versionado.
- **Código fuente:** Blueprints por feature (backend) / NgModules por feature (frontend), como se definió en Patrones de Implementación (Paso 5).
- **Tests:** `backend/tests/` reflejando la estructura de `app/`; frontend con `*.spec.ts` co-ubicados (igual que sico-web).
- **Assets:** no aplica assets estáticos pesados para el MVP (sin imágenes de marca ni fuentes propias todavía).

### Development Workflow Integration

**Servidor de desarrollo:** `backend/` corre con el servidor de desarrollo de Flask (`flask run`) en local; `frontend/` con `ng serve` (puerto libre, ej. 4300 para no chocar con sico-web en 4200 si se corren ambos localmente).

**Build:** `frontend/` compila con `ng build`; `backend/` no requiere build (Python interpretado), solo instalación de dependencias (`requirements.txt`).

**Despliegue:** contenedor Docker por subproyecto (backend y frontend), siguiendo el patrón ya usado por los microservicios Java — un puerto expuesto por contenedor en ECS/EC2. `docker-compose.yml` en la raíz es solo para desarrollo local, no para producción.
