- source_spec: `_bmad-output/implementation-artifacts/spec-11-2-feedback-distinto-al-superar-un-reto.md`
  summary: Levantar un harness de pruebas para el módulo guiado (`frontend/src/app/guided/**`) — hoy no tiene ni un solo spec.
  evidence: Story 11.2 modificó markup/estado con animación (`.verdict.passed`, reset de `challengeVerdict`) sin ningún test que lo proteja. `GuidedLessonComponent` inyecta 5 servicios (`GuidedService`, `NotebookService`, `UserProfileService`, `TourService`, `ActivatedRoute`) más varios componentes hijo en su plantilla — levantar el harness completo es un esfuerzo desproporcionado al alcance de una historia de CSS/plantilla puntual, pero sigue siendo un hueco real de cobertura para cualquier cambio futuro en este componente.

- source_spec: `_bmad-output/implementation-artifacts/spec-11-1-ver-el-progreso-de-las-6-lecciones-como-un-mapa.md`
  summary: `guided-home` no muestra ningún mensaje cuando `lessons` queda vacío por un error de API (distinto del estado `loading`) — el `<ol>`/mapa se renderiza sin hijos y sin explicación.
  evidence: Preexistente, no introducido por la Story 11.1 — la plantilla anterior (`.lesson-list` + `@for`) tenía exactamente el mismo hueco sobre el mismo arreglo `lessons` vacío. El manejo de error de `guided.listLessons()` ya deja `loading = false` sin poblar `lessons` ni fijar ningún mensaje de error.

- source_spec: `_bmad-output/implementation-artifacts/spec-endurecer-seguridad-analisis-y-aprendizaje.md`
  summary: Con agregación "Promediar", el Pareto calcula % del total, % acumulado y 80/20 sobre la suma de promedios, lo que no tiene lectura estadística; evaluar ocultar esas columnas o ponderar.
  evidence: Revisión pasada 2 #22; la matriz congelada define "Pareto sobre la media por grupo", así que cambiarlo requiere decisión del dueño.
- source_spec: `_bmad-output/implementation-artifacts/spec-endurecer-seguridad-analisis-y-aprendizaje.md`
  summary: backend/app/convatec/routes.py sigue leyendo X-Session-Id del cliente con fallback "anonymous"; migrarlo a app/utils/session.py si se reactiva Convatec.
  evidence: Revisión pasada 2 #32; el blueprint está desconectado en app/__init__.py y la spec prohíbe tocar Convatec.
