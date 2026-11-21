# Epic 12 Context: Análisis en un clic

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Quien sube un Excel al módulo sin código debe ver el tablero automático de inmediato — sin clics intermedios si el archivo ya está limpio, con uno solo si necesita limpieza — en vez del flujo actual que siempre exige un clic adicional de "Confirmar y generar análisis" después de ver la clasificación sugerida de columnas. Esto importa porque, al inspeccionar el código, se confirmó que el paso de limpieza del Excel ya resuelve el caso "usable" sin clic; el único punto de fricción real que queda es el paso de clasificación de columnas, que hoy siempre bloquea aunque la sugerencia ya se calculó sola. La corrección humana no desaparece — porque la clasificación automática puede equivocarse (caso documentado: encabezado mal detectado que produce columnas sin nombre) — sino que se mueve de "antes del resultado" a "un panel encima del resultado".

## Stories

- Story 12.1: Ver el tablero automático sin esperar un clic de confirmación
- Story 12.2: Corregir la clasificación de una columna después de ver el tablero
- Story 12.3: Mensaje informativo en vez de formulario bloqueante

## Requirements & Constraints

- El perfilado de Excel ya emite un veredicto de 3 estados (`usable`, `usable_con_limpieza`, `no_usable`); esta épica no cambia esa lógica, solo se apoya en ella.
- Con veredicto `usable`, el DataFrame ya se vincula sin confirmación humana (comportamiento existente, sin cambios).
- Con veredicto `usable_con_limpieza`, el único clic permitido en todo el flujo es el de confirmar la limpieza del Excel — la clasificación de columnas ya no debe pedir un segundo clic aparte.
- La sugerencia de rol por columna (dimensión/métrica/fecha/identificador/descartar) ya se calcula sola en cuanto se conoce el perfil, con o sin asistente de IA disponible — esta épica solo cambia cuándo se actúa sobre ese resultado, no cómo se calcula.
- Un error al generar el análisis automático debe seguir mostrándose con un mensaje claro sin romper la sesión (manejo de error ya existente, sin cambios).
- El flujo debe minimizar clics sin eliminar la posibilidad de corregir una clasificación equivocada — esta es la razón de ser de la épica, no un efecto secundario.
- El notebook libre y el módulo guiado no cambian — el alcance es exclusivo del módulo sin código.

## Technical Decisions

- Cero cambios de backend: la generación de la clasificación sugerida y la construcción del catálogo de análisis a partir de una clasificación ya soportan este flujo tal como están. Todo el trabajo es de frontend, en el home del módulo sin código y en el componente compartido de clasificación de columnas.
- El evento que hoy solo se dispara al hacer clic en el botón de confirmar debe emitirse automáticamente en cuanto la sugerencia de clasificación termina de calcularse, disparando la generación del análisis sin esperar esa interacción.
- El botón y los selectores de rol por columna se conservan como mecanismo de corrección, pero dejan de ser un formulario bloqueante previo al resultado.
- Corregir una columna después de ver el tablero **regenera el catálogo completo** (todo-o-nada), reutilizando el mismo mecanismo de generación ya existente — no se construye ni se necesita un modo incremental que parchee un solo bloque, dado el volumen de datos típico de este proyecto.
- No se agrega ninguna señal de confianza por columna al backend: la clasificación semántica sigue devolviendo únicamente un indicador global de si se usó el asistente de IA, nunca una confianza por columna. La alternativa de auto-confirmar siempre y esconder el paso de clasificación fue evaluada y descartada por esto mismo.
- Explícitamente fuera de alcance: no se modifican el tablero de análisis ni el componente de gráficas interactivas del módulo sin código (incluye un fix de Zone.js/NgZone ya en producción, que no debe revertirse ni evadirse).

## UX & Interaction Patterns

- El panel de clasificación de columnas pasa de formulario bloqueante previo al resultado a panel de corrección visible junto al tablero ya generado.
- El copy cambia de una instrucción de confirmación obligatoria a un mensaje informativo (tono: "así se interpretó el archivo"), con un llamado a la acción para corregir que se percibe como opcional, no como paso obligatorio — distinto en tono del botón de confirmación anterior.
- El mecanismo de selección de rol por columna (selector editable por fila) se mantiene igual; solo cambia el momento y el marco en que se presenta.
- Caso de referencia para validar la corrección: el archivo con encabezado mal detectado que produce columnas sin nombre reconocible sigue siendo la prueba de fuego para este flujo.

## Cross-Story Dependencies

- Story 12.2 y 12.3 dependen de que 12.1 ya dispare el tablero automáticamente: el reposicionamiento del panel de corrección y el cambio de copy solo tienen sentido una vez que el resultado ya está visible por defecto.
- Sin dependencias con las Épicas 9, 10 ni 11. Depende de que las Épicas 4-8 (perfilado, clasificación semántica, catálogo automático) sigan funcionando sin cambios — esta épica no las modifica, solo cambia cuándo se invocan desde el frontend.
