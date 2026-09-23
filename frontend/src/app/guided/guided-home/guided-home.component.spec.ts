import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { of } from 'rxjs';

import { UserProfileService } from '../../core/user-profile.service';
import { LessonSummary } from '../../models/api.models';
import { GuidedService } from '../services/guided.service';
import { GuidedHomeComponent } from './guided-home.component';

// Story 11.1: unit test de la derivación de estado del mapa - cubre los 3
// escenarios de la tabla I/O del spec (primera visita, progreso a mitad,
// curso terminado). No usa TestBed: la lógica es puramente de datos
// (lessons + isComplete()), así que se instancia el componente directo con
// stubs de sus dos dependencias.
describe('GuidedHomeComponent - lessonsWithState', () => {
  const lessons: LessonSummary[] = [
    { id: 'l0', title: 'Lección 0', summary: '', usa_datos_reales: false },
    { id: 'l1', title: 'Lección 1', summary: '', usa_datos_reales: false },
    { id: 'l2', title: 'Lección 2', summary: '', usa_datos_reales: false },
    { id: 'l3', title: 'Lección 3', summary: '', usa_datos_reales: false },
    { id: 'l4', title: 'Lección 4', summary: '', usa_datos_reales: false },
    { id: 'l5', title: 'Lección 5', summary: '', usa_datos_reales: false },
  ];

  function buildComponent(completedIds: string[]): GuidedHomeComponent {
    const guidedStub = {} as GuidedService;
    const profileStub = {
      isLessonComplete: (id: string) => completedIds.includes(id),
    } as UserProfileService;
    const component = new GuidedHomeComponent(guidedStub, profileStub);
    component.lessons = lessons;
    component.loading = false;
    return component;
  }

  it('primera visita (ninguna lección completa): lección 0 es actual, 1-5 bloqueadas', () => {
    const component = buildComponent([]);

    const states = component.lessonsWithState.map((item) => item.state);

    expect(states).toEqual(['actual', 'bloqueada', 'bloqueada', 'bloqueada', 'bloqueada', 'bloqueada']);
  });

  it('progreso a mitad (lecciones 0-2 completas): lección 3 es actual, 0-2 completadas, 4-5 bloqueadas', () => {
    const component = buildComponent(['l0', 'l1', 'l2']);

    const states = component.lessonsWithState.map((item) => item.state);

    expect(states).toEqual(['completada', 'completada', 'completada', 'actual', 'bloqueada', 'bloqueada']);
  });

  it('curso terminado (las 6 completas): ninguna se marca como actual ni bloqueada', () => {
    const component = buildComponent(lessons.map((lesson) => lesson.id));

    const states = component.lessonsWithState.map((item) => item.state);

    expect(states).toEqual(new Array(6).fill('completada'));
    expect(states).not.toContain('actual');
    expect(states).not.toContain('bloqueada');
  });
});

// Review finding (verification-gap + blind-hunter): the getter-only spec
// above never renders the template, so it can't catch a broken wiring
// between computed state and the attributes that actually gate navigation
// (routerLink/aria-disabled) or the "Actual" badge - this covers that.
describe('GuidedHomeComponent - rendered template', () => {
  let fixture: ComponentFixture<GuidedHomeComponent>;
  let component: GuidedHomeComponent;

  const lessons: LessonSummary[] = [
    { id: 'l0', title: 'Lección 0', summary: 'resumen 0', usa_datos_reales: true },
    { id: 'l1', title: 'Lección 1', summary: 'resumen 1', usa_datos_reales: false },
    { id: 'l2', title: 'Lección 2', summary: 'resumen 2', usa_datos_reales: false },
  ];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RouterTestingModule],
      declarations: [GuidedHomeComponent],
      providers: [
        { provide: GuidedService, useValue: { listLessons: () => of({ data: { lessons: [] } }) } },
        { provide: UserProfileService, useValue: { isLessonComplete: (id: string) => id === 'l0' } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GuidedHomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();

    // Bypass the stubbed HTTP round-trip and drive the template directly
    // with a known lessons array (l0 completada, l1 actual, l2 bloqueada
    // per the isLessonComplete stub above).
    component.lessons = lessons;
    component.loading = false;
    fixture.detectChanges();
  });

  function nodeAt(index: number): HTMLLIElement {
    return fixture.nativeElement.querySelectorAll('.lesson-node')[index] as HTMLLIElement;
  }

  it('does not render an active routerLink for a bloqueada lesson (no click-through)', () => {
    const blockedLink = nodeAt(2).querySelector('a.lesson-card') as HTMLAnchorElement;
    expect(blockedLink.getAttribute('href')).toBeNull();
    expect(blockedLink.getAttribute('aria-disabled')).toBe('true');
  });

  it('renders a working routerLink for actual and completada lessons', () => {
    const completedLink = nodeAt(0).querySelector('a.lesson-card') as HTMLAnchorElement;
    const actualLink = nodeAt(1).querySelector('a.lesson-card') as HTMLAnchorElement;
    expect(completedLink.getAttribute('href')).toBe('/guiado/l0');
    expect(actualLink.getAttribute('href')).toBe('/guiado/l1');
  });

  it('shows the "Actual" badge only on the actual lesson', () => {
    expect(nodeAt(0).querySelector('.badge')).toBeNull();
    expect(nodeAt(1).querySelector('.badge')?.textContent).toContain('Actual');
    expect(nodeAt(2).querySelector('.badge')).toBeNull();
  });

  it('gives every state a screen-reader-only text announcement', () => {
    expect(nodeAt(0).querySelector('.sr-only')?.textContent).toContain('completada');
    expect(nodeAt(1).querySelector('.sr-only')?.textContent).toContain('actual');
    expect(nodeAt(2).querySelector('.sr-only')?.textContent).toContain('bloqueada');
  });

  it('shows a visible lock hint on a bloqueada card, not just a hover title', () => {
    expect(nodeAt(2).querySelector('.lock-hint')).toBeTruthy();
    expect(nodeAt(0).querySelector('.lock-hint')).toBeNull();
  });

  // Story 11.3: cada tarjeta indica si esta lección va a sustituir el
  // ejemplo sintético por los datos reales de sico ya subidos en esta
  // sesión (item.lesson.usa_datos_reales, calculado en el backend).
  it('shows "Con tus datos de SICO" for a lesson with usa_datos_reales true, "Ejemplo" otherwise', () => {
    expect(nodeAt(0).querySelector('.data-source')?.textContent).toContain('Con tus datos de SICO');
    expect(nodeAt(1).querySelector('.data-source')?.textContent).toContain('Ejemplo');
    expect(nodeAt(1).querySelector('.data-source')?.textContent).not.toContain('Con tus datos de SICO');
    expect(nodeAt(2).querySelector('.data-source')?.textContent).toContain('Ejemplo');
  });
});
