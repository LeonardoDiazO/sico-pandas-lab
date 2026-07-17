import { TourStep } from '../../core/tour.service';

export const NOTEBOOK_TOUR_STEPS: TourStep[] = [
  {
    target: '.toolbar .restart',
    title: 'Reiniciar sesión',
    text:
      'Si algo quedó en mal estado, este botón borra tus variables de Python y empieza de cero. ' +
      'Tus datos en la base de sico NO se modifican -- todo aquí es de solo lectura.',
  },
  {
    target: 'app-data-source-panel',
    title: 'Traer tus datos',
    text:
      'Busca una tabla de sico y presiona "cargar", o sube un Excel. Cada tabla queda disponible ' +
      "como una variable llamada df_<nombre_de_la_tabla>.",
  },
  {
    target: 'app-loaded-variables',
    title: 'Qué tienes cargado',
    text: 'Aquí siempre ves qué variables (tablas) tienes disponibles ahora mismo, y cuántas columnas tiene cada una.',
  },
  {
    target: 'app-saved-queries',
    title: 'Mis consultas guardadas',
    text:
      'Cuando armes un análisis que te sirva, guárdalo con nombre (botón "💾 Guardar" en cualquier celda) y ' +
      'aquí queda listo para insertarlo de nuevo cuando lo necesites, sin reescribirlo.',
  },
  {
    target: 'app-chart-helper',
    title: 'Ayudante de gráficas',
    text:
      '¿Quieres una gráfica pero no recuerdas la sintaxis? Elige el tipo, la tabla y las columnas aquí -- ' +
      'se inserta el código real como una celda nueva, editable, para que aprendas viéndolo en acción.',
  },
  {
    target: 'app-code-cell',
    title: 'Una celda de código',
    text: 'Escribe código Python y presiona ▶ (o Ctrl/Cmd+Enter) para ejecutarlo. El resultado aparece justo debajo.',
  },
  {
    target: '.save-btn',
    title: 'Guardar esta celda',
    text: '¿Este código te sirve para más adelante? Guárdalo con un nombre y aparecerá en "Mis consultas guardadas".',
  },
  {
    target: '.add-cell',
    title: 'Más celdas',
    text: 'Agrega tantas celdas como quieras para seguir practicando.',
  },
];
