import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';

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
      imports: [FormsModule],
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
});
