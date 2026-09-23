import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chart } from 'chart.js';

import { ChartCanvasComponent } from './chart-canvas.component';

describe('ChartCanvasComponent', () => {
  let fixture: ComponentFixture<ChartCanvasComponent>;
  let component: ChartCanvasComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ChartCanvasComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ChartCanvasComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    fixture.destroy();
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
