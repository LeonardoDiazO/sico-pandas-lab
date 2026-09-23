import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chart } from 'chart.js';
import type { LineAnnotationOptions } from 'chartjs-plugin-annotation';

import { ChartCanvasComponent } from './chart-canvas.component';

describe('ChartCanvasComponent', () => {
  let fixture: ComponentFixture<ChartCanvasComponent>;
  let component: ChartCanvasComponent;

  let originalMatchMedia: typeof window.matchMedia;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ChartCanvasComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ChartCanvasComponent);
    component = fixture.componentInstance;

    // Headless Chrome (as run in CI/this test suite) reports
    // prefers-reduced-motion as matching by default, unlike a real browser
    // with no OS preference set - pin it to "no preference" here so every
    // test gets the deliberate, deterministic animation duration unless it
    // explicitly opts into the reduced-motion path below.
    originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({ matches: false, media: query }) as MediaQueryList) as typeof window.matchMedia;
  });

  afterEach(() => {
    fixture.destroy();
    window.matchMedia = originalMatchMedia;
  });

  it('maps result_records into bar values (parsing money-formatted strings) and a % acumulado line', () => {
    component.records = [
      { Vendedor: 'Ana', Neto: '$ 1.200', '% acumulado': 60 },
      { Vendedor: 'Luis', Neto: 800, '% acumulado': 100 },
    ];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const chart = Chart.getChart(canvas);

    expect(chart).toBeTruthy();
    expect(chart!.data.labels).toEqual(['Ana', 'Luis']);
    expect(chart!.data.datasets[0].data).toEqual([1200, 800]);
    expect(chart!.data.datasets[1].data).toEqual([60, 100]);
  });

  it('produces NaN (a chart gap), not a misleading 0, for an unparseable value', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 'n/a', '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const chart = Chart.getChart(canvas);

    expect(chart!.data.datasets[0].data[0]).toBeNaN();
  });

  it('formats the tooltip label: money prefix for money columns, decimals kept for others, % for the line, and a placeholder for missing data', () => {
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    const barContext = { dataset: { type: 'bar', label: 'Neto' }, parsed: { y: 1200 } } as any;
    expect((component as any).formatTooltipLabel(barContext)).toBe('Neto: $ 1.200');

    component.valueKey = 'Promedio';
    const nonMoneyContext = { dataset: { type: 'bar', label: 'Promedio' }, parsed: { y: 1234.56 } } as any;
    expect((component as any).formatTooltipLabel(nonMoneyContext)).toBe('Promedio: 1.234,56');

    const lineContext = { dataset: { type: 'line', label: '% acumulado' }, parsed: { y: 82.5 } } as any;
    expect((component as any).formatTooltipLabel(lineContext)).toBe('% acumulado: 82.5%');

    const missingContext = { dataset: { type: 'bar', label: 'Promedio' }, parsed: { y: null } } as any;
    expect((component as any).formatTooltipLabel(missingContext)).toBe('Promedio: sin dato');
  });

  it('animates in under 1 second (explicit duration, not relying on Chart.js default)', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const chart = Chart.getChart(canvas);
    const animation = chart!.options.animation as { duration?: number; easing?: string };
    // Exact values, not just "under 1000" - a regression that widened this
    // to e.g. 950ms would still pass a bounds-only check while defeating
    // the story's intent of a snappy, deliberately-chosen duration.
    expect(animation?.duration).toBe(700);
    expect(animation?.easing).toBe('easeOutQuart');
  });

  it('reuses the same Chart instance on data changes instead of creating a duplicate', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';
    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const firstChart = Chart.getChart(canvas);

    component.records = [
      { Vendedor: 'Ana', Neto: 100, '% acumulado': 50 },
      { Vendedor: 'Luis', Neto: 200, '% acumulado': 100 },
    ];
    component.ngOnChanges({});
    fixture.detectChanges();

    const secondChart = Chart.getChart(canvas);
    expect(secondChart).toBe(firstChart);
    expect(secondChart!.data.labels).toEqual(['Ana', 'Luis']);
    // The story's own claim (Implementation Notes) is that the animation
    // config applies "tanto a la creación inicial como a cada
    // regeneración" - assert that here instead of only in the
    // creation-only test above.
    expect((secondChart!.options.animation as { duration?: number })?.duration).toBe(700);
  });

  it('disables animation when the OS/browser requests reduced motion', () => {
    window.matchMedia = ((query: string) => ({ matches: true, media: query }) as MediaQueryList) as typeof window.matchMedia;

    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';
    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const chart = Chart.getChart(canvas);
    expect((chart!.options.animation as { duration?: number })?.duration).toBe(0);
  });

  function getLine80Annotation(canvas: HTMLCanvasElement): LineAnnotationOptions {
    const chart = Chart.getChart(canvas);
    const annotations = (chart!.options.plugins as { annotation?: { annotations?: Record<string, unknown> } })
      ?.annotation?.annotations;
    return annotations?.['line80'] as LineAnnotationOptions;
  }

  it('draws an 80% reference line annotation on the cumulative axis, with a visible label', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const line80 = getLine80Annotation(canvas);

    expect(line80).toBeTruthy();
    expect(line80.yMin).toBe(80);
    expect(line80.yMax).toBe(80);
    expect(line80.yScaleID).toBe('y1');
    expect(line80.label?.display).toBe(true);
    expect(line80.label?.content).toBe('80%');
  });

  it('keeps the 80% annotation after regenerating with different data (update path, not just creation)', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';
    fixture.detectChanges();

    component.records = [
      { Vendedor: 'Ana', Neto: 100, '% acumulado': 50 },
      { Vendedor: 'Luis', Neto: 200, '% acumulado': 100 },
    ];
    component.ngOnChanges({});
    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    const line80 = getLine80Annotation(canvas);
    expect(line80?.yMin).toBe(80);
  });

  it('sets an aria-label on the canvas summarizing the chart', () => {
    component.records = [{ Vendedor: 'Ana', Neto: 100, '% acumulado': 100 }];
    component.categoryKey = 'Vendedor';
    component.valueKey = 'Neto';

    fixture.detectChanges();

    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    expect(canvas.getAttribute('aria-label')).toContain('Neto');
    expect(canvas.getAttribute('aria-label')).toContain('Vendedor');
  });
});
