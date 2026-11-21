---
status: 'analysis'
completedAt: '2026-09-21'
inputDocuments: ['prd-sico-pandas-lab-2026-07-12.md', 'analisis-modulo-nocode-sico-pandas-lab-2026-07-18.md', 'epics-modulo-nocode-sico-pandas-lab-2026-07-18.md', 'epics-epic9-kpis-ejecutivos-sico-pandas-lab-2026-07-30.md', 'sprint-status-sico-pandas-lab.yaml']
relatedTo: 'Mesa redonda (bmad-party-mode) 2026-09-21, a pedido del dueño del producto: la app funciona (Épicas 4-8 done) pero no "da gusto usar" a nivel visual e interactivo. Nunca se corrió bmad-ux en este proyecto.'
---

# sico-pandas-lab — Interactividad y UX del módulo guiado y del módulo sin código

Análisis discutido en mesa redonda (analista, PM, UX, arquitecto, dev). Objetivo:
identificar por qué la app se siente "funcional pero plana" pese a que las Épicas
4-8 (sin código) y 3 (guiado) ya están implementadas, y proponer mejoras concretas
de interactividad/UX con alcance técnico realista.

## El hallazgo que reordena las ideas sueltas

Las dos peticiones del dueño del producto ("mejora el guiado" y "mejora el
dashboard de IA") parecían un solo pedido de "más brillo visual", pero al
inspeccionar el código son **dos problemas de naturaleza distinta**:

- **Módulo sin código:** el problema no es estético, es de arquitectura de datos.
  Las gráficas (`no-code-chart.component.html:100`, `[innerHTML]="safeChartSvg"`)
  son imágenes SVG estáticas generadas server-side por matplotlib/seaborn
  (`backend/app/notebook/chart_builder.py`). No hay tooltip, zoom ni drill-down
  posible porque el frontend nunca recibe los datos, solo una imagen ya
  renderizada. No se arregla con CSS.
- **Módulo guiado:** el problema sí es de UX pura. `guided-home.component.html`
  tiene 11 líneas: una lista de tarjetas con un ✓. No hay sensación de progreso,
  ni celebración al pasar un reto (`guided-lesson.component` reutiliza el mismo
  `cell-result.component` que el notebook libre, sin distinguir "correcto" de
  "aquí está tu output"). Aquí sí basta con trabajo de frontend.

Tratarlos como el mismo problema habría llevado a una sola solución genérica
("más animaciones") que no resuelve ninguno de los dos bien. Se separan en dos
épicas.

**Dato de arquitectura que despeja la discusión:** `frontend/package.json` no
tiene ninguna librería de gráficos (ni Chart.js, ni D3, ni Plotly, ni
ngx-charts). No es una migración, es la primera decisión de este tipo que toma
el proyecto.

---

## Épica 10 — Gráficos interactivos en el módulo sin código

**Objetivo:** que las gráficas del tablero automático (Pareto y afines)
respondan al usuario — tooltip con el valor exacto, animación de entrada, línea
de corte del 80% marcada — en vez de ser una foto.

**Decisión de arquitectura (con desacuerdo real en la mesa, resuelto):**
Plotly.js se descartó por peso (~1MB sin tree-shaking) frente a Chart.js
(~60KB), que ya trae tooltips y animaciones de fábrica y cubre barra/línea/
histograma sin problema. Plotly queda abierto para el futuro si aparece una
necesidad real de mapas de calor o 3D — no hoy.

**Decisión de alcance (no negociable):** el notebook libre (Épicas 1-3) **no**
se toca. Ahí el SVG de matplotlib es correcto a propósito: el usuario escribe
código real y debe ver exactamente lo que su script produjo. La interactividad
aplica solo al tablero automático del módulo sin código.

**Alcance técnico:**
- Backend: `execution.py` ya expone `result_records` (agregado para las
  tarjetas KPI de resúmenes de baja cardinalidad) — extender ese mecanismo para
  que los bloques de tipo gráfica del `analysis-dashboard` también viajen como
  datos crudos, no solo como imagen, cuando el consumidor sea el módulo sin
  código.
- Frontend: nueva dependencia Chart.js en `no-code-chart.component` y
  `analysis-dashboard.component`. Tema leído desde los `--token` de
  `src/styles.scss` vía `Chart.defaults` en runtime, para no crear una segunda
  paleta.
- Anotación de línea del 80% acumulado usando `chartjs-plugin-annotation`
  (reutiliza el cálculo que ya existe en el flujo Pareto de la Épica 8).

**Criterios de aceptación clave:**
- Un Pareto generado desde el módulo sin código muestra tooltip al pasar el
  mouse sobre cada barra, con el valor y el % acumulado.
- La gráfica anima su entrada (no aparece de golpe).
- El notebook libre sigue generando SVG server-side sin cambios de
  comportamiento.
- Los colores del gráfico usan los tokens existentes, no valores sueltos.

---

## Épica 11 — Progreso y feedback en el módulo guiado

**Objetivo:** que avanzar en las 6 lecciones se sienta como progreso real, no
como marcar casillas en una lista.

**Decisión de UX (no negociable):** feedback de reto correcto ≠ feedback de
reto ejecutado. Hoy ambos casos usan el mismo `cell-result.component` sin
distinción visual. Un reto que pasa la validación del servidor
(`backend/app/guided/challenges.py`) debe reaccionar de forma distinta a un
reto que simplemente corrió sin error.

**Decisión de alcance (con desacuerdo real, resuelto):** se propuso una racha/
contador de sesión (motivación tipo Duolingo). Se descarta para este corte —
implica lógica de tiempo/sesión que no existe hoy y abre una pregunta de diseño
sin resolver (¿resetear racha desincentiva a alguien que usa esto
esporádicamente en el trabajo?). Queda anotada como candidata a una futura
Épica 12, no bloquea esta.

**Alcance técnico:**
- Frontend: rediseño de `guided-home.component` — de lista vertical a mapa de
  lecciones tipo camino, con 3 estados visuales (completada / actual /
  bloqueada) conectados por líneas.
- `guided-lesson.component`: nuevo estado visual de "reto superado" (borde,
  transición, micro-mensaje contextual) distinto del resultado crudo de
  ejecución — no reemplaza `cell-result.component`, lo envuelve para este caso.
- Cada tarjeta de lección indica si usa datos reales de SICO o ejemplo
  sintético — el dato ya existe en `backend/app/guided/data_context.py`, es
  solo exponerlo y pintarlo; no requiere trabajo nuevo de backend.

**Criterios de aceptación clave:**
- Desde `guided-home`, el usuario ve de un vistazo cuáles lecciones completó,
  cuál es la actual y si alguna está bloqueada por prerequisito.
- Pasar un reto dispara una transición y un mensaje distinto a simplemente ver
  el resultado de una celda.
- La tarjeta de cada lección distingue "con tus datos de SICO" vs. "ejemplo
  sintético".

---

## Nota transversal (no es una épica aparte)

El pulido visual general (micro-interacciones, estados vacíos con más
carácter, transiciones consistentes) no se trata como iniciativa separada —
se exige como criterio de aceptación dentro de las Épicas 10 y 11, para que no
quede como "algún día" sin dueño.

## Relación con trabajo ya planeado

Ninguna de las dos épicas reemplaza ni bloquea la Épica 9 (KPIs ejecutivos,
backlog). Comparten el dato `result_records` de `execution.py`, pero KPIs
ejecutivos es agregación numérica y esto es interactividad de presentación —
se numeran 10 y 11 para no forzarlas dentro del alcance ya escrito de la 9.
