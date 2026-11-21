# Epic 10 Context: Gráficos interactivos en el módulo sin código

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Quien sube un Excel al módulo sin código y llega al tablero automático hoy solo ve una imagen estática (SVG/matplotlib) sin ninguna interacción posible. Esta épica reemplaza esas gráficas por visualizaciones interactivas: tooltip con el valor exacto (y % acumulado en el Pareto), animación de entrada al renderizarse, y una anotación visual marcando dónde el Pareto cruza el 80% acumulado. El objetivo es que el tablero automático se sienta vivo y responda al usuario, en vez de ser una foto fija — sin tocar el notebook libre, que conserva su comportamiento actual a propósito.

## Stories

- Story 10.1: Migrar el tablero automático a gráficas interactivas con datos crudos
- Story 10.2: Ver tooltip con valor exacto en las gráficas
- Story 10.3: Animación de entrada al generar una gráfica
- Story 10.4: Línea de corte del 80% en el Pareto
- Story 10.5: Colores del gráfico alineados a los design tokens

## Requirements & Constraints

- La gráfica sin código y el resumen Pareto con % acumulado (funcionalidad ya existente) se **extienden** con interactividad, no se reemplazan ni cambian su cálculo.
- No hay objetivo formal de tiempo de respuesta, pero cargar la nueva librería de gráficos no debe percibirse como un retraso notable al renderizar el tablero.
- Los nuevos elementos visuales (tooltips, anotaciones) deben mantener un nivel básico razonable de accesibilidad (contraste, navegación por teclado), sin exigir cumplimiento formal WCAG.
- Si la librería de gráficos falla al renderizar, el sistema debe degradar a un mensaje de error claro, nunca a una pantalla en blanco.
- Criterio de no-regresión explícito: el notebook libre (gráficas generadas server-side) no cambia su comportamiento ni su contrato de respuesta.
- El pulido visual (micro-interacciones, estados con más carácter) es un criterio de aceptación exigido en las historias de esta épica, no trabajo opcional sin dueño.

## Technical Decisions

- Se elige **Chart.js** (~60KB) sobre Plotly (~1MB sin tree-shaking) como librería de gráficos del frontend; hoy no existe ninguna librería de gráficos instalada en el proyecto, así que esta es la primera decisión de este tipo, no una migración. Plotly queda abierto a futuro solo si aparece necesidad real de mapas de calor o 3D.
- El backend extiende el mecanismo ya existente que expone datos crudos por bloque de resultado (usado hoy para tarjetas KPI) para que los bloques de tipo gráfica del tablero automático también viajen como datos crudos (categorías, valores, acumulado), en vez de crear un mecanismo paralelo.
- Toda respuesta backend nueva o extendida para servir estos datos usa el wrapper de respuesta estándar de la API existente.
- El tema de colores de Chart.js se configura en runtime leyendo los tokens de diseño compartidos del stylesheet global de la app — no se declara una paleta nueva ni colores sueltos.
- La anotación de la línea del 80% en el Pareto se implementa con un plugin de anotaciones de Chart.js, reutilizando el cálculo de % acumulado que ya existe en el flujo Pareto implementado previamente.
- El alcance de cambios de frontend se limita a los componentes de gráfica y tablero del módulo sin código; el generador de gráficas server-side del notebook libre no se modifica.
- El frontend sigue el patrón existente de módulos por feature con servicios y estado reactivo — no se introduce un store nuevo para el estado de las gráficas.

## UX & Interaction Patterns

- Al pasar el mouse sobre una barra o segmento de una gráfica del tablero automático aparece un tooltip con el valor exacto; si la gráfica es un Pareto, también muestra el % acumulado hasta ese punto. En dispositivos táctiles (sin hover), el tooltip aparece al tocar la barra.
- La gráfica anima su entrada al renderizarse por primera vez, en menos de 1 segundo; si se regenera (por ejemplo, al cambiar de columna), la animación se repite sin duplicar elementos visuales en pantalla.
- El Pareto muestra una anotación (línea más etiqueta "80%") en el punto donde el acumulado cruza ese umbral, usando el color de énfasis de los tokens de diseño.
- Los colores de cualquier gráfica interactiva del tablero automático provienen de los tokens de diseño compartidos de la app, nunca de valores hardcodeados nuevos.

## Cross-Story Dependencies

- Story 10.1 es la base técnica de toda la épica: migra el tablero a Chart.js con datos crudos. Las Stories 10.2, 10.3, 10.4 y 10.5 dependen de que 10.1 esté implementada, ya que todas actúan sobre la gráfica interactiva que 10.1 introduce.
- No hay dependencias entre esta épica y la Épica 11 (progreso y feedback del módulo guiado). Ambas asumen que las épicas de módulo sin código y guiado ya implementadas previamente están completas.
