import { TourStep } from '../../core/tour.service';

export const GUIDED_TOUR_STEPS: TourStep[] = [
  {
    target: '.back',
    title: 'Todas las lecciones',
    text: 'Desde aquí vuelves en cualquier momento a la lista completa de lecciones.',
  },
  {
    target: '.lesson-data',
    title: 'Practicar con tus datos (opcional)',
    text:
      'Ábrelo para subir tu Excel o cargar una tabla de sico y practicar con datos reales. Si no cargas nada, ' +
      'cada paso usa un ejemplo pequeño automáticamente, así que siempre puedes seguir la lección.',
  },
  {
    target: '.lesson-progress',
    title: 'Tu avance',
    text:
      'Cada barra es una página de la lección: los pasos, el reto y el cierre. Se ponen en verde cuando los ' +
      'completas, y puedes tocar cualquiera para ir directo a ella.',
  },
  {
    target: '.lesson-page.current .step',
    title: 'Un paso a la vez',
    text:
      'Cada paso trae una explicación en lenguaje sencillo y una celda con código real ya escrito: ' +
      'ejecútala para ver qué hace, y cámbiala para experimentar, no se rompe nada.',
  },
  {
    target: '.wizard-nav',
    title: 'Avanzar sin bajar',
    text:
      'Con «Siguiente» pasas al próximo paso, al reto y al cierre de la lección, donde está la siguiente lección. ' +
      'El reto se revisa automáticamente al presionar «Comprobar reto».',
  },
];
