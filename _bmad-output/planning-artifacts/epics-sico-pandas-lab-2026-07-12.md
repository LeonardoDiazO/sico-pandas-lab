---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete'
completedAt: '2026-07-12'
inputDocuments: ['prd-sico-pandas-lab-2026-07-12.md', 'architecture-sico-pandas-lab-2026-07-12.md']
---

# sico-pandas-lab - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for sico-pandas-lab, decomposing the requirements from the PRD and Architecture requirements into implementable stories. No UX Design document exists for this project (no UX-DR section).

## Requirements Inventory

### Functional Requirements

**Nota de alcance:** FR1 y FR2 (login y gestión de usuarios) se movieron a Growth — el MVP inicial tiene acceso abierto (sin autenticación) para desplegar rápido en Render.com y validar con el dueño.

FR4: Un usuario puede cargar un archivo Excel como fuente de datos para practicar.
FR5: Un usuario puede conectarse al esquema `sco` y ver/seleccionar las tablas disponibles (`02_movcabeza`, `02_movimiento`, `02_item`, `02_itemprecios`) mediante un panel de conexión en la parte superior de la interfaz.
FR6: Un usuario puede cargar los datos de una o varias tablas de la base de datos como un DataFrame de pandas dentro de su notebook.
FR6b: Un usuario puede ejecutar consultas combinadas (joins) entre dos, tres o las tablas que requiera del esquema `sco`.
FR7: El sistema impide cualquier operación de escritura (INSERT/UPDATE/DELETE/DDL) sobre la base de datos de producción, sin importar el código que el usuario ejecute.
FR8: Un usuario puede crear y editar celdas de código Python/pandas.
FR9: Un usuario puede ejecutar una celda de código de forma individual y ver su resultado (tabla, texto, error o gráfica).
FR10: Un usuario puede ejecutar celdas en el orden que elija dentro de su sesión.
FR11: Un usuario puede ver mensajes de error claros cuando su código falla, sin que la sesión se rompa ni afecte a otros usuarios.
FR12: Un usuario puede generar gráficas (líneas, barras, dispersión, histogramas, etc.) a partir de un DataFrame.
FR13: Un usuario puede reiniciar su notebook/sesión para empezar de nuevo.
FR14: Un usuario puede acceder a un módulo guiado con ejemplos paso a paso usando datos reales de sico.
FR15: El módulo guiado explica qué hace cada bloque de código pandas mostrado.
FR16: Un usuario puede ejecutar los ejemplos del módulo guiado por su cuenta, celda por celda.
FR17: Un usuario puede pasar del módulo guiado al notebook de práctica libre para aplicar lo aprendido con otros datos.
FR18: El sistema ejecuta el código de cada usuario en un entorno aislado (sandbox) por sesión.
FR19: El sistema impone límites de tiempo y recursos por ejecución de celda.
FR20: Las credenciales de conexión a la base de datos nunca son visibles ni accesibles desde el código que el usuario escribe.
FR21: El sistema verifica automáticamente al arrancar que el usuario de base de datos configurado tiene únicamente privilegios SELECT sobre las tablas autorizadas, y se niega a iniciar si detecta cualquier otro privilegio.

### NonFunctional Requirements

NFR1 (Security): Todo acceso a la RDS MariaDB debe realizarse con un usuario de solo-lectura (SELECT) a nivel de motor de BD — no negociable.
NFR2 (Security): El código de usuario corre en sandbox aislado por sesión, sin acceso al filesystem del servidor ni a las credenciales de BD.
NFR3 (Security): Credenciales de RDS gestionadas como secretos del backend, nunca en el frontend ni expuestas al código del usuario.
NFR4 (Security): Aislamiento entre sesiones de usuario (uno no puede ver/afectar el notebook de otro).
NFR5 (Performance): Ejecución de celda con respuesta en tiempo razonable (~5-10s sugerido, a confirmar con volumen real de datos).
NFR6 (Performance/Scalability): No se requiere optimización de alta concurrencia — 2-3 usuarios simultáneos como máximo esperado.
NFR7 (Reliability): Sin SLA formal; disponibilidad razonable en horario laboral es suficiente. Fallos de conexión a la RDS deben mostrarse como error claro sin exponer detalles técnicos sensibles.
NFR8 (Accessibility): Nivel básico razonable (contraste, navegación por teclado), sin objetivo formal de cumplimiento WCAG.
NFR9 (Integration): Conexión estable a la RDS desde el entorno de despliegue del backend; modelo de auth desacoplado para no bloquear futura integración SSO con sico-web.

### Additional Requirements

- **⚠️ Despliegue MVP (decisión revisada): Render.com**, no ECS/EC2 — dos Web Services (backend, frontend) desplegados vía modo Docker de Render, para preservar portabilidad hacia ECS en Growth.
- **⚠️ Sin autenticación en el MVP:** acceso abierto a la URL. Riesgo aceptado explícitamente (solo-lectura + URL no difundida). Login queda diseñado pero no se construye hasta Growth.
- **Starter/inicialización (Arquitectura, Paso 3):** proyecto monorepo con `backend/` (Flask 3.1.3, patrón application factory + Blueprints) y `frontend/` (Angular 20.2.x + Angular Material, NgModules calcado de sico-web) — la inicialización de ambos es la primera historia de implementación.
- **Motor de ejecución (Decisión #1, bloqueante):** worker Python persistente por sesión, comunicación por IPC, límites de CPU/memoria vía `resource.setrlimit`. Modelo de amenaza explícito: protege contra accidentes de usuarios internos confiables, no es un sandbox contra atacantes maliciosos.
- **Acceso a datos:** conexión de solo-lectura vía PyMySQL + `pandas.read_sql` (sin ORM) a `sco.02_movcabeza`, `sco.02_movimiento`, `sco.02_item`, `sco.02_itemprecios`. Usuario de BD dedicado — **bloqueante**: no usar la cuenta `admin` compartida.
- **BD propia de la app:** SQLite + SQLAlchemy 2.0.51 ORM (usuarios/roles), con `PRAGMA journal_mode=WAL` activado explícitamente.
- **Autenticación MVP:** Flask-Login 0.6.3 + sesión de servidor + hash de contraseña con `werkzeug.security`. Roles: Usuario y Super Admin.
- **Editor de celdas:** Monaco Editor vía `ngx-monaco-editor-v2` (verificar issue conocido de comportamiento en Angular 20 antes de comprometerse).
- **Gráficas:** matplotlib/seaborn en el backend → PNG base64 en la respuesta JSON → `<img>` en el frontend (sin librería de charting en Angular).
- **Contrato de API:** wrapper `ApiResponse` calcado de `mappale-http-utils` (`{ message, data, success, status }`), servido siempre a través de una única función helper `api_response(...)`.
- **Despliegue:** contenedor Docker por subproyecto, un puerto expuesto, mismo patrón que los microservicios Java (ECS sobre EC2).
- **Health-check no negociable:** verificación automática de privilegios de solo-lectura al arrancar (FR21), con prueba automatizada explícita (`tests/test_startup_checks.py`).
- **Decisiones abiertas que bloquean la capa de datos:** (1) confirmar si se fuerza TLS hacia la RDS, (2) conseguir/crear el usuario de MariaDB de solo-lectura acotado a las 4 tablas.
- **Fuera de alcance del MVP (Growth):** login (Flask-Login + SQLite), gestión de usuarios vía script, migración de Render a ECS/EC2, SSO con sico-web/`mappale_security`, streaming real de ejecución (WebSocket/SSE), aislamiento por contenedor (gVisor/CodeJail), panel de administración de usuarios, gráficas interactivas (Plotly).

### UX Design Requirements

No aplica — no existe documento de UX Design para este proyecto.

### FR Coverage Map

FR4: Epic 1, Story 1.4 - Cargar Excel como fuente de datos
FR8: Epic 1 - Crear/editar celdas de código
FR9: Epic 1 - Ejecutar celda individual y ver resultado
FR10: Epic 1 - Ejecutar celdas en cualquier orden
FR11: Epic 1 - Mensajes de error claros
FR12: Epic 1, Story 1.5 - Generar gráficas desde un DataFrame
FR13: Epic 1 - Reiniciar notebook/sesión
FR18: Epic 1 - Ejecución aislada por sesión (sandbox)
FR19: Epic 1 - Límites de tiempo/recursos por celda
FR5: Epic 2 - Panel de conexión al esquema `sco` y selección de tablas
FR6: Epic 2 - Cargar tabla(s) de sico como DataFrame
FR6b: Epic 2 - Consultas combinadas (joins) entre tablas de `sco`
FR7: Epic 2 - Bloqueo de operaciones de escritura sobre producción
FR20: Epic 2 - Credenciales de la RDS nunca expuestas al código del usuario
FR21: Epic 2 - Verificación automática de privilegios de solo-lectura al arrancar
FR14: Epic 3 - Acceso al módulo guiado con datos reales
FR15: Epic 3 - Explicación de cada bloque de código
FR16: Epic 3 - Ejecutar ejemplos guiados por cuenta propia
FR17: Epic 3 - Transición del módulo guiado al notebook libre

## Epic List

### Epic 1: Notebook de Práctica con Datos Propios (Excel)
El usuario puede escribir y ejecutar código Python/pandas en un notebook seguro, cargando sus propios datos desde Excel, viendo resultados y gráficas. Incluye la inicialización de ambos proyectos base (Flask + Angular) y el despliegue en Render.com como parte del "definition of done" de esta épica — es la primera versión completa y desplegable de la herramienta.
**FRs covered:** FR4, FR8, FR9, FR10, FR11, FR12, FR13, FR18, FR19

### Epic 2: Datos Reales de Sico (Solo Lectura)
El usuario puede conectarse al esquema `sco`, seleccionar una o varias tablas (con joins entre ellas) y traerlas como DataFrame dentro del notebook de la Épica 1, reemplazando el Excel genérico por datos reales del negocio. El sistema verifica automáticamente al arrancar que el acceso sigue siendo estrictamente de solo lectura.
**FRs covered:** FR5, FR6, FR6b, FR7, FR20, FR21

### Epic 3: Módulo de Aprendizaje Guiado
El usuario de nivel básico sigue un módulo guiado con ejemplos paso a paso usando datos reales de sico, entiende qué hace cada bloque de código, y transiciona al notebook libre para aplicar lo aprendido con sus propios datos.
**FRs covered:** FR14, FR15, FR16, FR17

## Epic 1: Notebook de Práctica con Datos Propios (Excel)

El usuario puede escribir y ejecutar código Python/pandas en un notebook seguro, cargando sus propios datos desde Excel, viendo resultados y gráficas. Incluye la inicialización de ambos proyectos base y el despliegue en Render.com.

### Story 1.1: Ver la aplicación desplegada y funcionando

As a persona interesada en el proyecto (ej. el dueño),
I want poder abrir una URL y ver que la aplicación está corriendo,
So that pueda confirmar que el desarrollo avanza sin necesitar acceso técnico.

**Acceptance Criteria:**

**Given** el backend (Flask, application factory) y el frontend (Angular, NgModules) están inicializados en el monorepo `sico-pandas-lab`
**When** se despliegan como dos Web Services en Render.com usando el modo Docker
**Then** la URL del frontend carga una pantalla básica de bienvenida
**And** la URL del backend responde en `/api/health` usando el wrapper `ApiResponse` (`{ message, data, success, status }`)

### Story 1.2: Crear y ejecutar celdas de código Python/pandas

As a usuario que practica pandas,
I want crear celdas de código y ejecutarlas individualmente,
So that pueda ver el resultado de mi código paso a paso, como en un notebook.

**Acceptance Criteria:**

**Given** estoy en el notebook de práctica libre
**When** agrego una celda de código y la ejecuto
**Then** veo su resultado (texto o tabla) debajo de la celda
**And** puedo ejecutar celdas en cualquier orden dentro de mi sesión, reutilizando el mismo worker persistente (`worker_manager.py`) en vez de crear un proceso nuevo por celda

**Given** mi código se ejecuta en el worker de mi sesión
**When** ejecuto una celda
**Then** el worker corre aislado con límites de tiempo, CPU y memoria vía `resource.setrlimit` (FR18, FR19)
**And** ese aislamiento no depende de ninguna conexión a base de datos externa

### Story 1.3: Ver errores de ejecución de forma clara y segura

As a usuario que comete un error de sintaxis o lógica en pandas,
I want ver un mensaje de error claro sin que se rompa mi sesión,
So that pueda corregir mi código y seguir practicando sin perder mi progreso.

**Acceptance Criteria:**

**Given** escribo código con un error de sintaxis o una excepción de Python
**When** ejecuto esa celda
**Then** veo el mensaje de error específico (tipo de excepción + descripción) en el panel de resultado de esa celda
**And** las variables ya definidas en celdas anteriores permanecen intactas

**Given** el error ocurre dentro de mi worker aislado
**When** se produce una excepción no controlada
**Then** el worker no afecta las sesiones de otros usuarios

### Story 1.4: Cargar un archivo Excel como fuente de datos

As a usuario que quiere practicar con sus propios datos,
I want subir un archivo Excel,
So that pueda cargarlo como un DataFrame de pandas y trabajar con él en mis celdas.

**Acceptance Criteria:**

**Given** estoy en el notebook de práctica libre
**When** subo un archivo `.xlsx` válido
**Then** el sistema lo carga como un DataFrame disponible en mi sesión (vía `pandas.read_excel`/`openpyxl`), con una variable predecible que puedo usar en mis celdas

**Given** subo un archivo que no es un Excel válido
**When** el sistema intenta procesarlo
**Then** muestro un mensaje de error claro sin romper mi sesión

### Story 1.5: Generar gráficas desde un DataFrame

As a usuario practicando pandas,
I want generar gráficas a partir de un DataFrame con mi propio código,
So that pueda visualizar mis datos como parte natural del aprendizaje de pandas.

**Acceptance Criteria:**

**Given** tengo un DataFrame cargado en mi sesión (ej. desde el Excel subido en la Story 1.4)
**When** ejecuto código que genera una figura con matplotlib/seaborn (ej. `df.plot()`)
**Then** la gráfica se muestra en el panel de resultado de la celda como una imagen

**Given** genero una gráfica
**When** se transporta del backend al frontend
**Then** viaja como PNG codificado en base64 dentro del `ApiResponse`
**And** el frontend la renderiza en un `<img>`, sin librerías de charting adicionales en Angular

### Story 1.6: Reiniciar mi notebook/sesión

As a usuario que quiere empezar de cero,
I want reiniciar mi notebook,
So that pueda limpiar el estado de mis variables y volver a intentar sin arrastrar errores previos.

**Acceptance Criteria:**

**Given** tengo una sesión activa con variables y celdas ejecutadas
**When** elijo la opción de reiniciar el notebook
**Then** el worker de mi sesión se termina explícitamente y se crea uno nuevo limpio, sin variables previas y sin procesos huérfanos

## Epic 2: Datos Reales de Sico (Solo Lectura)

El usuario puede conectarse al esquema `sco`, seleccionar una o varias tablas (con joins entre ellas) y traerlas como DataFrame dentro del notebook de la Épica 1. El sistema verifica automáticamente al arrancar que el acceso sigue siendo estrictamente de solo lectura.

**Relaciones del esquema `sco` (ver Arquitectura para el detalle completo):** `02_movcabeza.indice = 02_movimiento.mov_indice` (+ `cia`), `02_movimiento.mov_item = 02_item.item_codigo` (+ `cia`), `02_item.item_codigo = 02_itemprecios.codigo_item` (+ `cia`). `02_itemprecios` es una tabla EAV (una fila por atributo/precio, no una sola fila por item).

### Story 2.1: Verificación automática de privilegios de solo-lectura al arrancar

As a responsable técnico del sistema,
I want que el backend verifique automáticamente sus privilegios de base de datos al arrancar,
So that nunca se ejecute con un usuario que tenga permisos de escritura sobre producción.

**Acceptance Criteria:**

**Given** el backend arranca con las credenciales de conexión a la RDS configuradas
**When** se ejecuta `startup_checks.py`
**Then** el sistema consulta los privilegios reales del usuario de BD configurado (vía `INFORMATION_SCHEMA.TABLE_PRIVILEGES` o equivalente)
**And** si detecta cualquier privilegio distinto de `SELECT` sobre las 4 tablas autorizadas, el backend se niega a arrancar y registra un error claro en el log

**Given** el usuario de BD tiene únicamente `SELECT` sobre las 4 tablas autorizadas
**When** se ejecuta el health-check
**Then** el backend arranca normalmente

**Given** este comportamiento es no negociable (Arquitectura, Paso 5)
**When** se implementa esta historia
**Then** debe incluir una prueba automatizada explícita en `tests/test_startup_checks.py`

### Story 2.2: Conectarse al esquema `sco` y ver las tablas disponibles

As a usuario,
I want ver un panel de conexión donde pueda seleccionar el esquema `sco` y las tablas disponibles,
So that sepa qué datos reales de sico puedo usar en mi notebook.

**Acceptance Criteria:**

**Given** estoy en el notebook
**When** abro el panel de conexión de datos (`data-source-panel`, parte superior de la interfaz)
**Then** veo listadas las 4 tablas autorizadas (`02_movcabeza`, `02_movimiento`, `02_item`, `02_itemprecios`) del esquema `sco`

**Given** selecciono una tabla
**When** confirmo la selección
**Then** el panel me indica que esa tabla está lista para cargarse en mi notebook

### Story 2.3: Cargar una tabla de sico como DataFrame

As a usuario,
I want cargar los datos de una tabla seleccionada como un DataFrame,
So that pueda analizarla con pandas igual que hago con mis datos de Excel.

**Acceptance Criteria:**

**Given** seleccioné una tabla en el panel de conexión
**When** confirmo la carga
**Then** el backend ejecuta un `SELECT` de solo lectura sobre esa tabla (vía `sico_client.py` + `pandas.read_sql`) y el resultado queda disponible como DataFrame en mi sesión

**Given** la tabla puede ser grande
**When** se carga
**Then** el backend aplica un límite razonable de filas por defecto (⚠️ valor exacto a definir en implementación) para no saturar el worker, informando al usuario si el resultado fue truncado

### Story 2.4: Ejecutar consultas combinadas (joins) entre tablas

As a usuario,
I want combinar dos, tres o las tablas que necesite del esquema `sco`,
So that pueda analizar relaciones reales entre movimientos, ítems y precios, no solo una tabla aislada.

**Acceptance Criteria:**

**Given** selecciono más de una tabla en el panel de conexión
**When** confirmo la combinación
**Then** el backend construye un JOIN de solo lectura usando las relaciones reales del esquema: `02_movcabeza.indice = 02_movimiento.mov_indice`, `02_movimiento.mov_item = 02_item.item_codigo`, `02_item.item_codigo = 02_itemprecios.codigo_item` — siempre incluyendo la columna de compañía (`cia`/`mov_cia`/`item_cia`) correspondiente en cada join
**And** el resultado queda disponible como un único DataFrame en mi sesión

**Given** `02_itemprecios` es una tabla EAV (una fila por atributo/precio, identificada por `tipo_campo_adicional`)
**When** la incluyo en una combinación
**Then** el resultado refleja múltiples filas por item (una por atributo), sin intentar aplanarlas automáticamente — el usuario decide cómo pivotearlas con su propio código pandas

### Story 2.5: Bloqueo de operaciones de escritura sobre producción

As a usuario que por error escribe código que intenta modificar datos,
I want que el sistema rechace cualquier operación de escritura sobre la base de datos de producción,
So that nunca ponga en riesgo los datos reales de sico, incluso por accidente.

**Acceptance Criteria:**

**Given** mi código intenta ejecutar un `INSERT`, `UPDATE`, `DELETE` o cualquier DDL sobre la conexión a sico
**When** se intenta ejecutar
**Then** la operación es rechazada tanto por los permisos reales de MariaDB (verificados en Story 2.1) como por el diseño de `sico_client.py`, y veo un mensaje de error claro en mi celda

**Given** la operación de escritura es rechazada
**When** ocurre
**Then** no se guarda ningún registro parcial ni se corrompe el estado de mi sesión

### Story 2.6: Credenciales de la RDS nunca expuestas al código del usuario

As a responsable de seguridad del sistema,
I want que las credenciales de conexión a la RDS nunca sean accesibles desde el código que el usuario escribe,
So that no se puedan filtrar ni usar indebidamente, incluso si un usuario intenta inspeccionar el entorno de ejecución.

**Acceptance Criteria:**

**Given** mi código se ejecuta en el worker de mi sesión
**When** intento leer variables de entorno o inspeccionar el proceso desde mi código Python
**Then** no encuentro las credenciales de conexión a la RDS (gestionadas exclusivamente en el backend, fuera del alcance del worker)

**Given** el backend necesita conectarse a la RDS
**When** ejecuta una consulta en nombre de mi sesión
**Then** usa una conexión ya autenticada que me expone solo un DataFrame resultado, nunca la cadena de conexión ni las credenciales crudas

## Epic 3: Módulo de Aprendizaje Guiado

El usuario de nivel básico sigue un módulo guiado con ejemplos paso a paso usando datos reales de sico, entiende qué hace cada bloque de código, y transiciona al notebook libre para aplicar lo aprendido con sus propios datos. Reutiliza el motor de ejecución (Épica 1) y el panel de conexión a datos (Épica 2) — no construye infraestructura nueva.

### Story 3.1: Acceder al módulo guiado con un ejemplo usando datos reales de sico

As a usuario de nivel básico de pandas,
I want acceder a un módulo guiado con un ejemplo paso a paso usando datos reales de sico,
So that pueda aprender el flujo completo (cargar → explorar → transformar → graficar) sin partir de cero.

**Acceptance Criteria:**

**Given** estoy en la app
**When** elijo el módulo guiado
**Then** veo un ejemplo estructurado paso a paso que usa una de las tablas reales del esquema `sco`, mediante el `data-source-panel` ya construido en la Épica 2

**Given** el ejemplo sigue el flujo cargar → explorar → transformar → graficar
**When** avanzo por el módulo
**Then** cada paso se presenta como una celda de código pre-armada dentro del mismo notebook, reutilizando el motor de ejecución de la Épica 1

### Story 3.2: Entender qué hace cada bloque de código del ejemplo

As a usuario de nivel básico,
I want que el módulo guiado explique qué hace cada bloque de código pandas mostrado,
So that entienda el "por qué", no solo copie y pegue.

**Acceptance Criteria:**

**Given** estoy viendo una celda del módulo guiado
**When** la reviso
**Then** encuentro una explicación en texto simple (sin jerga técnica) de qué hace esa línea/bloque de pandas, ubicada junto a la celda

**Given** avanzo entre pasos del módulo
**When** cambio de celda
**Then** la explicación cambia junto con el código mostrado, manteniendo coherencia entre ambos

### Story 3.3: Ejecutar los ejemplos guiados por cuenta propia

As a usuario de nivel básico,
I want ejecutar yo mismo cada celda del ejemplo guiado, celda por celda,
So that practique realmente el flujo, no solo lo lea pasivamente.

**Acceptance Criteria:**

**Given** estoy en un paso del módulo guiado con una celda de código
**When** ejecuto esa celda
**Then** veo el resultado real (tabla, gráfica o error) usando el mismo motor de ejecución del notebook libre (worker persistente, aislamiento, límites de recursos — Épica 1)

**Given** aún no he ejecutado la celda actual
**When** intento avanzar al siguiente paso
**Then** el sistema me anima a ejecutarla primero, sin bloquear el avance (sugerencia de UX, no una restricción dura)

### Story 3.4: Pasar del módulo guiado al notebook libre

As a usuario que terminó (o está en medio) del módulo guiado,
I want pasar al notebook de práctica libre conservando lo aprendido,
So that pueda aplicar el flujo con mis propios datos o tablas, sin perder el contexto.

**Acceptance Criteria:**

**Given** estoy en el módulo guiado
**When** elijo "continuar en práctica libre"
**Then** se abre el notebook libre (Épica 1) con acceso al mismo panel de conexión de datos (Épica 2) para elegir mis propios datos

**Given** transiciono al notebook libre
**When** llego ahí
**Then** el código del ejemplo guiado no se copia automáticamente a mi notebook libre (decisión de alcance MVP: mantenerlo simple, el usuario reescribe basándose en lo aprendido)
