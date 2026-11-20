import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';

import { NotebookDraftService } from '../../core/notebook-draft.service';

import { AnalysisBlock, AnalysisSummary } from '../../models/api.models';
import { AnalysisBlockComponent } from '../analysis-block/analysis-block.component';
import { CellResultComponent } from '../cell-result/cell-result.component';
import { ChartCanvasComponent } from '../chart-canvas/chart-canvas.component';
import { AnalysisDashboardComponent } from './analysis-dashboard.component';

describe('AnalysisDashboardComponent', () => {
  let fixture: ComponentFixture<AnalysisDashboardComponent>;
  let component: AnalysisDashboardComponent;

  // Story 10.1 fixture: a bloque with non-empty result_records (the shape
  // table_builder.py's build_summary_code actually returns) - the case
  // that must show the Chart.js canvas instead of the static chart_svg.
  const bloque: AnalysisBlock = {
    titulo: 'Neto por Vendedor',
    dimension: 'Vendedor',
    metrica: 'Neto',
    insight: '3 de 5 vendedores concentran el 82% del total.',
    resultado: {
      stdout: null,
      result_html: '<table></table>',
      result_text: null,
      result_records: [
        { Vendedor: 'Ana', Neto: '$ 1.200', '% acumulado': 60 },
        { Vendedor: 'Luis', Neto: '$ 800', '% acumulado': 100 },
      ],
      chart_svg: '<svg><title>Pareto</title></svg>',
      error: null,
      explanation: 'Explicación de prueba.',
    },
  };

  const resumen: AnalysisSummary = { filas: 10, dimensiones: 1, metricas: 1, bloques: 1 };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FormsModule, RouterModule.forRoot([])],
      declarations: [AnalysisDashboardComponent, AnalysisBlockComponent, CellResultComponent, ChartCanvasComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AnalysisDashboardComponent);
    component = fixture.componentInstance;
    component.bloques = [bloque];
    component.resumen = resumen;
    component.ngOnChanges();
    fixture.detectChanges();
  });

  it('passes hideChart to app-cell-result and mounts app-chart-canvas, never showing both charts', () => {
    const compiled = fixture.nativeElement as HTMLElement;

    // cell-result's own chart_svg wrapper (class "chart", see
    // cell-result.component.html) must be absent - hideChart suppressed it.
    expect(compiled.querySelector('.chart')).toBeNull();
    // The matplotlib chart_svg (it has a <title>) must not render anywhere;
    // the only SVGs left are the toolbar's own icons.
    expect(compiled.querySelector('svg title')).toBeNull();

    // The interactive replacement must be present instead.
    expect(compiled.querySelector('app-chart-canvas canvas')).not.toBeNull();
  });

  it('shows the lifted insight and switches a card to the table view with exact values', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.insight')?.textContent).toContain('3 de 5 vendedores');

    const tableButton = Array.from(compiled.querySelectorAll<HTMLButtonElement>('app-analysis-block .seg')).find(
      (b) => b.textContent?.trim() === 'Tabla',
    )!;
    tableButton.click();
    fixture.detectChanges();

    const cells = Array.from(compiled.querySelectorAll('.data-table tbody td')).map((td) => td.textContent?.trim());
    expect(cells).toContain('Ana');
    expect(cells).toContain('$ 1.200');
  });

  it('explains dimensions the catalog left out instead of dropping them silently', () => {
    component.resumen = { ...resumen, omitidas: [{ dimension: 'Cliente', valores: 79 }] };
    fixture.detectChanges();
    const notice = (fixture.nativeElement as HTMLElement).querySelector('.notice');
    expect(notice?.textContent).toContain('Cliente');
    expect(notice?.textContent).toContain('79');
  });

  function blockWith(extra: Partial<AnalysisBlock>): AnalysisBlock {
    return { ...bloque, ...extra };
  }

  function render(bloques: AnalysisBlock[], res: AnalysisSummary = resumen) {
    component.bloques = bloques;
    component.resumen = res;
    component.ngOnChanges();
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('"Ver el código" queues the card code and opens the Notebook', () => {
    const draft = TestBed.inject(NotebookDraftService);
    const router = TestBed.inject(Router);
    spyOn(draft, 'enqueue');
    const nav = spyOn(router, 'navigate').and.resolveTo(true);
    const code = "# Neto por Vendedor\ndf.groupby('Vendedor')['Neto'].sum()";
    const el = render([blockWith({ codigo: code })]);

    (el.querySelector('.code-btn') as HTMLButtonElement).click();

    expect(draft.enqueue).toHaveBeenCalledWith(code);
    expect(nav).toHaveBeenCalledWith(['/notebook']);
  });

  it('lists the groups left out of the ranking', () => {
    const el = render([blockWith({ fueraDelRanking: [{ grupo: '(vacío)', valor: '$ 50', motivo: 'filas sin categoría' }] })]);
    const text = el.querySelector('.out-of-ranking')?.textContent ?? '';
    expect(text).toContain('(vacío)');
    expect(text).toContain('$ 50');
    expect(text).toContain('filas sin categoría');
    expect(text).not.toContain('[object Object]');
  });

  it('selecting a category and choosing "Filtrar" asks the parent to re-run with that filter', () => {
    let emitted: unknown = null;
    component.filtersChange.subscribe((f) => (emitted = f));
    render([bloque]);
    const block = fixture.debugElement.query((d) => d.name === 'app-analysis-block').componentInstance as AnalysisBlockComponent;
    block.select(0);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.filter-btn') as HTMLButtonElement).click();
    expect(emitted).toEqual([{ column: 'Vendedor', values: ['Ana'] }]);
  });

  it('shows the active filter as a removable chip', () => {
    let emitted: unknown = null;
    component.filtersChange.subscribe((f) => (emitted = f));
    const el = render([bloque], { ...resumen, filtros: [{ column: 'Ciudad', values: ['Cali'] }] });
    expect(el.querySelector('.filter-chip')?.textContent).toContain('Ciudad = Cali');
    (el.querySelector('.filter-chip button') as HTMLButtonElement).click();
    expect(emitted).toEqual([]);
  });

  it('a trend block offers the line view and never a "Filtrar" action', () => {
    const trend = blockWith({
      tipo: 'tendencia',
      titulo: 'Tendencia mensual de Neto por Fecha',
      // The block reports the date COLUMN; its records are keyed by "Mes".
      dimension: 'Fecha',
      resultado: {
        ...bloque.resultado,
        result_records: [
          { Mes: '2026-01', Neto: 100 },
          { Mes: '2026-02', Neto: 150 },
        ],
      },
    });
    render([trend]);
    const block = fixture.debugElement.query((d) => d.name === 'app-analysis-block').componentInstance as AnalysisBlockComponent;
    expect(block.views.map((v) => v.value)).toEqual(['tendencia', 'tabla']);
    expect(block.chartView).toBe('tendencia');
    expect(block.rows.map((r) => r.label)).toEqual(['2026-01', '2026-02']);
    block.select(1);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.filter-btn')).toBeNull();
  });

  it('keeps the filter chip visible when the filter leaves no cards', () => {
    const el = render([], { ...resumen, bloques: 0, filtros: [{ column: 'Vendedor', values: ['Ana'] }] });
    expect(el.querySelector('.filter-chip')?.textContent).toContain('Vendedor = Ana');
  });
});
