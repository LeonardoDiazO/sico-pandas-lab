---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedAt: '2026-07-12'
inputDocuments: []
workflowType: 'prd'
outputFile: '_bmad-output/prd-sico-pandas-lab-2026-07-12.md'
classification:
  projectType: web_app
  domain: edtech
  complexity: medium_high
  projectContext: greenfield
  notes: 'Notebook interactivo estilo Colab para practicar pandas. 2-3 usuarios internos, nivel básico. Fuentes de datos: Excel subido o conexión solo-lectura a RDS MariaDB de producción (mappale-sico). Requiere sandboxing seguro para ejecución de código Python arbitrario. Módulo de aprendizaje guiado + módulo de práctica libre. Integración futura (fuera de alcance inicial) con sico-web (https://sico.mappale.co/), posible SSO compartido más adelante. No aplican regulaciones de privacidad estudiantil (COPPA/FERPA) — es herramienta interna corporativa, no plataforma educativa pública.'
---

# PRD: sico-pandas-lab — Notebook de Práctica de Pandas

Repositorio: `REPOSITORIOS/sico-pandas-lab` — proyecto standalone, deliberadamente **no adjunto** a la arquitectura oficial de SICO (no usa el sufijo `-bc`/`-or`) hasta que el dueño apruebe su desarrollo/integración.

**Author:** Maximun_neo
**Date:** 2026-07-12

## Executive Summary

Herramienta web interna, tipo notebook (similar a Google Colab), para que 2-3 personas del equipo practiquen Python y pandas generando gráficas a partir de datos reales, en lugar de CSVs sueltos y desconectados. La fuente de datos fidedigna es la base de datos de producción MariaDB en AWS RDS (`<endpoint-de-la-rds-de-sico>`), a la que la app se conecta en **modo solo-lectura**; alternativamente el usuario puede trabajar con un archivo Excel descargado/subido. Los usuarios tienen nivel básico de pandas, por lo que la app debe maximizar su curva de aprendizaje.

**Posicionamiento:** vive como repositorio standalone (`sico-pandas-lab`), deliberadamente **no adjunto** a la arquitectura oficial de SICO (sin sufijo `-bc`/`-or`) hasta que el dueño del producto apruebe su desarrollo e integración formal.

### What Makes This Special

A diferencia de Colab con CSVs genéricos, esta herramienta viene preconectada a la fuente de verdad real del negocio (el esquema de sico), permitiendo practicar con datos que el equipo ya conoce y usa. Combina dos modos de uso: (1) un **notebook de práctica libre** donde el usuario escribe y ejecuta código celda por celda para generar sus propias gráficas, y (2) un **módulo guiado con ejemplos**, pensado para nivel básico, que enseña el flujo completo (cargar datos → explorar → transformar → graficar) paso a paso. El insight central: se aprende pandas más rápido analizando datos reales del propio negocio que con datasets de tutorial, y de paso el equipo se familiariza con el esquema de datos de sico antes de la futura integración con **sico-web** (https://sico.mappale.co/).

## Project Classification

- **Tipo de proyecto:** Web App (SPA tipo notebook interactivo)
- **Dominio:** Edtech (herramienta interna de práctica/aprendizaje, no plataforma educativa pública — no aplican COPPA/FERPA)
- **Complejidad:** Media-alta (ejecución segura de código Python arbitrario + conexión solo-lectura a base de datos de producción)
- **Contexto:** Greenfield (app nueva; integración con sico-web queda fuera del alcance inicial)

## Success Criteria

### User Success

- Cada usuario logra conectarse a una fuente de datos (Excel o RDS) y generar su primera gráfica desde su propio código en la primera sesión.
- El momento "aha": ver una gráfica generada con datos reales de sico, no con un dataset genérico de tutorial.
- Un usuario de nivel básico completa el módulo guiado y queda en capacidad de repetir el flujo (cargar → explorar → transformar → graficar) por su cuenta, con sus propios datos.

### Business Success

- ⚠️ Supuesto a validar: a 3 meses, las 2-3 personas objetivo usan la app de forma recurrente (ej. semanal) para practicar — no se definió cadencia exacta en la conversación.
- El equipo gana autonomía para generar sus propios análisis y gráficas de datos de sico, sin depender de que otra persona les prepare CSVs o reportes (confirmado como visión).
- Reemplazo del flujo actual (Colab + CSVs sueltos) como método de práctica del equipo.

### Technical Success

- Conexión solo-lectura a la RDS MariaDB (`mappale-sico`) estable, sin riesgo de escritura accidental sobre datos de producción.
- Ejecución de código Python/pandas en un entorno aislado (sandbox) que no exponga credenciales de la base de datos ni permita fuga de datos entre usuarios.
- Ambas fuentes de datos (Excel y RDS) funcionan con la misma experiencia de práctica, sin fricción para el usuario.

### Measurable Outcomes

- ⚠️ Supuesto a validar: 100% de los usuarios objetivo (2-3 personas) completan el módulo guiado en su primera semana de acceso.
- ⚠️ Supuesto a validar: 0 incidentes de escritura o modificación accidental sobre la base de datos de producción.

## Product Scope

### MVP - Minimum Viable Product

- Notebook de práctica libre: celdas de código editables y ejecutables, con salida de gráficas.
- Módulo guiado con ejemplos, orientado a nivel básico de pandas.
- Panel de conexión al esquema `sco` con selección de tablas (`02_movcabeza`, `02_movimiento`, `02_item`, `02_itemprecios`).
- Consultas combinadas (joins) entre dos, tres o las tablas que se requieran del esquema `sco`.
- Conexión solo-lectura a la RDS MariaDB (mappale-sico) alineada a su esquema.
- Carga de archivo Excel como fuente de datos alternativa.
- **Sin autenticación:** acceso abierto a quien tenga la URL, para desplegar rápido y validar con el dueño antes de invertir en login.
- **Despliegue en Render.com** (no ECS/EC2 todavía) — prioriza velocidad para tener algo funcional que mostrar; migración a ECS/EC2 queda para cuando se apruebe la integración formal con SICO.

### Growth Features (Post-MVP)

- Login simple (Flask-Login + SQLite) antes de dar acceso oficial a las 2-3 personas del equipo.
- Gestión de cuentas de usuario vía script/comando (FR2 original).
- Migración de despliegue de Render.com a AWS ECS/EC2, alineado con el patrón de los microservicios Java existentes.
- Integración de autenticación/SSO con sico-web.
- Guardado y versionado de notebooks por usuario.
- Módulos guiados adicionales por tema (limpieza de datos, agregaciones, series de tiempo, etc.).
- Panel de actividad para Super Admin (quién ha usado la app y cuándo).

### Vision (Future)

- Integración completa con sico-web como módulo de analítica/autoservicio para más usuarios del equipo.
- Exportar o compartir notebooks/gráficas generadas entre usuarios.

## User Journeys

⚠️ Supuesto a validar: nombres y detalles de personas son ilustrativos (no se conversaron nombres reales); la estructura y los puntos de fricción sí se derivan de lo discutido.

### Journey 1 — Práctica guiada (camino feliz, usuario nivel básico)

**Usuaria:** "Marcela", parte del equipo, nivel básico de pandas. Hoy practica en Google Colab con CSVs sueltos que no representan los datos reales de sico.

- **Escena inicial:** Marcela entra a la app, elige el **módulo guiado**, y ve un ejemplo paso a paso (cargar datos → explorar → transformar → graficar) usando una tabla real de la BD de sico (solo lectura).
- **Acción ascendente:** Sigue el ejemplo escribiendo y ejecutando cada celda ella misma; el módulo le explica qué hace cada línea de pandas.
- **Clímax:** Genera su primera gráfica con datos reales del negocio — el momento "esto es justo lo que necesitaba", muy distinto a un dataset genérico.
- **Resolución:** Termina el módulo con un flujo replicable que puede aplicar por su cuenta en el notebook libre.

**Capacidades reveladas:** módulo guiado con contenido paso a paso, conexión solo-lectura a la BD con datos reales, ejecución de celdas, generación de gráficas.

### Journey 2 — Práctica libre con error de código (caso borde)

**Usuario:** "Andrés", ya completó el módulo guiado y quiere explorar por su cuenta en el notebook libre, consultando una tabla distinta de sico.

- **Escena inicial:** Andrés abre un notebook libre y escribe una consulta/transformación propia sobre una tabla real.
- **Acción ascendente:** Comete un error de sintaxis en pandas y, por accidente, intenta una operación de escritura sobre la conexión a la BD (ej. un `UPDATE` mental trasladado a código).
- **Punto crítico:** La app debe rechazar cualquier intento de escritura (la conexión es solo-lectura) y mostrar un mensaje de error claro, sin bloquear ni afectar la sesión ni los datos de producción.
- **Resolución:** Andrés corrige su código, entiende el límite de solo-lectura, y continúa practicando sin haber puesto en riesgo los datos reales.

**Capacidades reveladas:** enforcement real de solo-lectura a nivel de conexión/BD (no solo UI), manejo de errores de ejecución de código claro y no destructivo, aislamiento de sesión entre usuarios (sandboxing).

### Journey 3 — Administración de acceso (Super Admin) — ⚠️ Growth, no aplica al MVP sin login

**Usuario:** Tú (Maximun_neo), como responsable de la herramienta y de sico.

- **Escena inicial:** Necesitas dar acceso a una nueva persona del equipo (dentro del rango de 2-3 usuarios) o revisar qué está pasando si alguien reporta un error de ejecución de código.
- **Acción ascendente:** Ejecutas un script/comando directo sobre la BD de usuarios (SQLite) para agregar o desactivar una cuenta — sin necesidad de una UI de administración para el MVP. Para la conexión a la BD de sico, el propio sistema verifica automáticamente al arrancar que sigue siendo estrictamente solo-lectura y se niega a iniciar si detecta lo contrario.
- **Clímax:** Confirmas que no hay riesgo para los datos de producción de sico y que el acceso está limitado a las personas correctas.
- **Resolución:** El equipo sigue practicando de forma segura, sin que administrar la herramienta te tome tiempo significativo.

**Capacidades reveladas:** gestión de usuarios vía script/comando (sin UI de administración en el MVP), verificación automática de privilegios de solo-lectura al arrancar el sistema (no requiere revisión manual).

### Journey Requirements Summary

- Conexión solo-lectura a MariaDB RDS con enforcement real (no solo restricción de UI).
- Notebook con ejecución de celdas aislada por usuario (sandboxing).
- Módulo guiado con contenido paso a paso usando datos reales de sico.
- Generación de gráficas a partir de resultados de pandas.
- Carga alternativa de archivo Excel.
- ⚠️ Gestión de usuarios/accesos vía script/comando manual — **movido a Growth**: el MVP inicial no tiene login (acceso abierto), por lo que no hay cuentas que gestionar todavía.
- Verificación automática de privilegios de solo-lectura al arrancar el sistema (sí es parte del MVP — FR21).
- Manejo de errores de ejecución claro y no destructivo.

## Domain-Specific Requirements

El dominio clasificado como edtech no trae consigo regulaciones de privacidad estudiantil aplicables (COPPA/FERPA no corresponden — es una herramienta interna, no una plataforma educativa pública). Sin embargo, la complejidad real de este proyecto viene de tocar una base de datos de producción real, no del dominio educativo en sí:

### Compliance & Regulatory
- No se identifican requisitos regulatorios externos (no hay datos de salud, pagos, ni menores de edad involucrados).
- ⚠️ Supuesto a validar: los datos en `mappale-sico` podrían incluir información sensible del negocio (financiera, de clientes/arrendatarios según el dominio de sico) — a confirmar en arquitectura si se requiere enmascarar o restringir columnas específicas antes de exponerlas a práctica.

### Technical Constraints
- **Solo-lectura real:** el usuario de base de datos que use la app debe tener permisos de solo `SELECT` a nivel de MariaDB (no solo restricción en la capa de aplicación), para que ningún error de código pueda escribir sobre producción.
- **Aislamiento de ejecución de código:** cada sesión de notebook debe correr en un entorno aislado (sandbox/contenedor) con límites de tiempo y recursos, para evitar que el código de un usuario afecte a otro o consuma recursos de forma descontrolada.
- **Manejo de credenciales:** las credenciales de conexión a la RDS nunca deben quedar expuestas al código que el usuario escribe o ejecuta.

### Integration Requirements
- Conexión de red hacia la RDS (`<endpoint-de-la-rds-de-sico>`) — ✅ confirmado en Arquitectura: acceso público con security group restringido por IP (no VPC privada).
- Integración futura con sico-web queda fuera de alcance del MVP, pero el modelo de usuarios/autenticación debería diseñarse pensando en no bloquear esa integración después.

### Risk Mitigations
- Riesgo: un usuario ejecuta código que intenta escribir en la BD → Mitigación: permisos de solo-lectura a nivel de motor de base de datos, no solo en la app.
- Riesgo: código de un usuario afecta la sesión de otro o consume recursos del servidor → Mitigación: sandboxing por sesión con límites de tiempo/CPU/memoria.
- Riesgo: exposición de datos sensibles del negocio a usuarios sin necesidad de verlos → Mitigación (a validar en arquitectura): revisar si todas las tablas/columnas de sico deben estar disponibles para práctica o si se requiere una vista/esquema de solo lectura filtrado.

## Web App Specific Requirements

### Project-Type Overview

SPA (single page application) con interfaz tipo notebook: panel de celdas de código ejecutables, panel de resultados (tablas/gráficas), y un módulo guiado separado con contenido paso a paso.

### Technical Architecture Considerations

- **SPA vs MPA:** SPA — la experiencia de notebook (ejecutar celda, ver resultado sin recargar página) requiere una aplicación de una sola página.
- **Soporte de navegadores:** ⚠️ Supuesto a validar: navegadores modernos (últimas versiones de Chrome/Edge/Firefox), sin necesidad de soportar navegadores antiguos dado que son solo 2-3 usuarios internos conocidos.
- **SEO:** No aplica — herramienta interna, no indexable ni pública.
- **Tiempo real:** No se requiere colaboración en tiempo real entre usuarios (cada quien practica en su propia sesión); la ejecución de celdas es síncrona, similar a Jupyter/Colab.
- **Accesibilidad:** ⚠️ Supuesto a validar: nivel básico razonable (contraste, navegación por teclado), sin un objetivo formal de cumplimiento WCAG dado el uso interno y acotado a pocas personas.

### Implementation Considerations

- El backend necesita un motor de ejecución de código Python/pandas por sesión (kernel aislado), no solo un frontend — esto es una decisión central de arquitectura (a definir en la fase de Create Architecture: ¿kernel tipo Jupyter embebido, contenedor por sesión, o ejecución en el navegador vía Pyodide/WASM?).
- La conexión a MariaDB debe vivir en el backend (nunca las credenciales en el navegador), exponiendo al notebook del usuario solo un objeto/conexión ya autenticada en modo solo-lectura.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**Enfoque MVP:** "Problem-solving MVP" — resolver el problema concreto de práctica desconectada (Colab + CSVs sueltos) conectando a datos reales, con el mínimo de superficie técnica necesaria para hacerlo de forma segura. No es un MVP de ingresos ni de plataforma; es una herramienta interna para validar que el equipo aprende mejor con datos reales.

**Requisitos de recursos:** ⚠️ Supuesto a validar: equipo pequeño (1-2 personas construyendo), sin fecha límite discutida explícitamente — a confirmar.

### MVP Feature Set (Phase 1)

**Journeys principales soportados:** Journey 1 (práctica guiada) y Journey 2 (práctica libre) de la sección de User Journeys.

**Capacidades imprescindibles:** ver lista completa en [Product Scope → MVP](#product-scope).

### Post-MVP Features

Ver [Product Scope → Growth Features](#product-scope) y [Vision](#product-scope) para el detalle de Fase 2 y Fase 3.

### Risk Mitigation Strategy

**Riesgos técnicos:** El mayor riesgo técnico es el motor de ejecución de código (sandboxing seguro + acceso solo-lectura real a la BD). Mitigación: resolverlo primero en la fase de arquitectura antes de construir el resto de la UI, ya que todo lo demás depende de que esta pieza sea segura.

**Riesgos de adopción:** Al ser solo 2-3 usuarios conocidos y con necesidad real ya expresada (reemplazar CSVs sueltos), el riesgo de adopción es bajo comparado con un producto de mercado abierto.

**Riesgos de recursos:** ⚠️ Supuesto a validar: si el tiempo de desarrollo es limitado, el módulo guiado (contenido educativo) podría recortarse primero, dejando el notebook de práctica libre con datos reales como el corazón innegociable del MVP.

## Functional Requirements

### Gestión de Usuarios y Acceso

- ~~FR1~~ (movido a Growth): login — la primera versión (demo/MVP) tiene **acceso abierto a quien tenga la URL**, sin autenticación, para desplegar rápido y mostrarle algo funcional al dueño. Se agrega login antes de dar acceso oficial a las 2-3 personas del equipo.
- ~~FR2~~ (movido a Growth): gestión de cuentas de usuario — no aplica sin login.
- ~~FR3~~ (eliminado): listar usuarios vía UI no se justifica para 2-3 cuentas gestionadas por script.

### Conexión a Fuentes de Datos

- FR4: Un usuario puede cargar un archivo Excel como fuente de datos para practicar.
- FR5: Un usuario puede conectarse al esquema `sco` y ver/seleccionar las tablas disponibles (`02_movcabeza`, `02_movimiento`, `02_item`, `02_itemprecios`) mediante un panel de conexión en la parte superior de la interfaz.
- FR6: Un usuario puede cargar los datos de una o varias tablas de la base de datos como un DataFrame de pandas dentro de su notebook.
- FR6b: Un usuario puede ejecutar consultas combinadas (joins) entre dos, tres o las tablas que requiera del esquema `sco`, no solo consultas de una tabla individual.
- FR7: El sistema impide cualquier operación de escritura (INSERT/UPDATE/DELETE/DDL) sobre la base de datos de producción, sin importar el código que el usuario ejecute.

### Notebook de Práctica Libre

- FR8: Un usuario puede crear y editar celdas de código Python/pandas.
- FR9: Un usuario puede ejecutar una celda de código de forma individual y ver su resultado (tabla, texto, error o gráfica).
- FR10: Un usuario puede ejecutar celdas en el orden que elija dentro de su sesión.
- FR11: Un usuario puede ver mensajes de error claros cuando su código falla, sin que la sesión se rompa ni afecte a otros usuarios.
- FR12: Un usuario puede generar gráficas (líneas, barras, dispersión, histogramas, etc.) a partir de un DataFrame.
- FR13: Un usuario puede reiniciar su notebook/sesión para empezar de nuevo.

### Módulo de Aprendizaje Guiado

- FR14: Un usuario puede acceder a un módulo guiado con ejemplos paso a paso usando datos reales de sico.
- FR15: El módulo guiado explica qué hace cada bloque de código pandas mostrado.
- FR16: Un usuario puede ejecutar los ejemplos del módulo guiado por su cuenta, celda por celda.
- FR17: Un usuario puede pasar del módulo guiado al notebook de práctica libre para aplicar lo aprendido con otros datos.

### Seguridad y Aislamiento de Ejecución

- FR18: El sistema ejecuta el código de cada usuario en un entorno aislado (sandbox) por sesión.
- FR19: El sistema impone límites de tiempo y recursos por ejecución de celda.
- FR20: Las credenciales de conexión a la base de datos nunca son visibles ni accesibles desde el código que el usuario escribe.

### Administración

- FR21: El sistema verifica automáticamente al arrancar que el usuario de base de datos configurado tiene únicamente privilegios `SELECT` sobre las tablas autorizadas, y se niega a iniciar si detecta cualquier otro privilegio (reemplaza la verificación manual por un Super Admin).

**Nota:** Este listado de FRs es el contrato de capacidades para el resto del PRD (UX, arquitectura, épicas). Cualquier capacidad no listada aquí deberá agregarse explícitamente más adelante.

## Non-Functional Requirements

### Security

- ⚠️ **Revisión de implementación:** no existe un usuario de solo-lectura dedicado; se conecta directo con las credenciales existentes (como DBeaver). Como no hay barrera a nivel de motor, la escritura se bloquea con: código de usuario sin acceso a la conexión, construcción exclusiva de `SELECT` con guarda dura `assert_select_only()` (rechaza DELETE/UPDATE/INSERT/DROP/TRUNCATE y sentencias encadenadas, con pruebas), y `SET SESSION TRANSACTION READ ONLY` en cada conexión. Uso de cuenta privilegiada es opt-in explícito (`SICO_ALLOW_WRITE_USER=true`). Idealmente (Growth) se crea un usuario de solo-lectura y se restablece el enforcement a nivel de motor.
- El código Python ejecutado por un usuario corre en un entorno aislado (sandbox) por sesión, sin acceso al sistema de archivos del servidor ni a las credenciales de conexión a la base de datos.
- Las credenciales de la RDS se gestionan como secretos del backend (variables de entorno o gestor de secretos), nunca embebidas en el frontend ni expuestas al código del usuario.
- Cada sesión de usuario está aislada de las demás (un usuario no puede ver ni afectar el notebook o los datos de otro usuario).
- ⚠️ **Riesgo aceptado explícitamente para el MVP:** sin login, cualquier persona con la URL puede consultar (solo-lectura) los datos de `sco`. Se acepta temporalmente porque (a) el acceso es estrictamente solo-lectura con enforcement a nivel de motor de BD, y (b) la URL no se difunde ampliamente — es una demo para validar con el dueño, no un lanzamiento público. Debe resolverse con login antes de dar acceso oficial al equipo.

### Performance

- ⚠️ Supuesto a validar: la ejecución de una celda de código debe devolver resultado (o error) en un tiempo razonable para no romper el flujo de aprendizaje — sugerido: menos de 5-10 segundos para operaciones típicas sobre datasets de tamaño moderado, a confirmar según el volumen real de datos de sico.
- Con solo 2-3 usuarios concurrentes esperados, no se requiere optimización para alta concurrencia en el MVP.

### Reliability

- ⚠️ Supuesto a validar: no se definió un SLA formal — al ser una herramienta interna de práctica (no crítica para operación del negocio), una disponibilidad razonable en horario laboral es suficiente para el MVP; no se requiere alta disponibilidad 24/7.
- Un fallo de conexión a la RDS debe mostrarse como un error claro al usuario, sin exponer detalles técnicos sensibles (cadenas de conexión, credenciales) en el mensaje de error.

### Scalability

- No es una prioridad para el MVP: el sistema solo necesita soportar 2-3 usuarios simultáneos. El diseño no debe sacrificar seguridad o simplicidad por una escalabilidad que no se necesita todavía.

### Accessibility

- ⚠️ Supuesto a validar: nivel básico de accesibilidad (contraste adecuado, navegación por teclado en los controles principales), sin un objetivo formal de cumplimiento WCAG dado el alcance interno y reducido de usuarios.

### Integration

- La conexión a la RDS MariaDB (`<endpoint-de-la-rds-de-sico>`) debe funcionar de forma estable desde el entorno donde se despliegue el backend — ✅ confirmado en Arquitectura: acceso público con security group restringido por IP.
- El modelo de usuarios/autenticación se diseña sin acoplarse rígidamente a un único proveedor, para no bloquear la futura integración (SSO) con sico-web (fuera de alcance del MVP).
