import { TourStep } from '../../core/tour.service';

export const GUIDED_TOUR_STEPS: TourStep[] = [
  {
    target: '.back',
    title: 'Todas las lecciones',
    text: 'Desde aquí vuelves en cualquier momento a la lista completa de lecciones.',
  },
  {
    target: 'app-data-source-panel',
    title: 'Traer tus datos',
    text:
      'Busca una tabla de sico y presiona "cargar" para practicar con datos reales -- si no cargas nada, ' +
      'cada paso usa un ejemplo pequeño automáticamente, así que siempre puedes seguir la lección.',
  },
  {
    target: 'app-loaded-variables',
    title: 'Qué tienes cargado',
    text: 'Aquí ves qué variables (tablas) están disponibles ahora mismo en tu sesión.',
  },
  {
    target: '.step',
    title: 'Pasos de la lección',
    text:
      'Cada paso trae una explicación en lenguaje sencillo y una celda con código real ya escrito -- ' +
      'ejecútala para ver qué hace, y cámbiala para experimentar, no se rompe nada.',
  },
  {
    target: '.challenge',
    title: 'Reto',
    text:
      'Algunas lecciones terminan en un Reto: una celda en blanco donde escribes tú la solución. ' +
      'Al presionar "Comprobar reto" se revisa automáticamente si tu resultado es correcto.',
  },
  {
    target: '.finish',
    title: 'Seguir avanzando',
    text: 'Aquí pasas a la siguiente lección cuando estés listo, o saltas al notebook libre para practicar con tus propios datos.',
  },
];
