import { Component, EventEmitter, Input, Output } from '@angular/core';

export interface KnownVariable {
  name: string;
  columns: string[];
}

type ChartKind = 'bar' | 'line' | 'hist' | 'scatter' | 'box';

const NEEDS_Y: Record<ChartKind, boolean> = {
  bar: true,
  line: true,
  hist: false,
  scatter: true,
  box: true,
};

const SEABORN_FN: Record<ChartKind, string> = {
  bar: 'barplot',
  line: 'lineplot',
  hist: 'histplot',
  scatter: 'scatterplot',
  box: 'boxplot',
};

const CHART_LABELS: { value: ChartKind; label: string }[] = [
  { value: 'bar', label: 'Barras (comparar categorías)' },
  { value: 'line', label: 'Línea (evolución/tendencia)' },
  { value: 'hist', label: 'Histograma (distribución de un valor)' },
  { value: 'scatter', label: 'Dispersión (relación entre dos números)' },
  { value: 'box', label: 'Caja (comparar distribuciones por grupo)' },
];

/**
 * Lets a beginner build a chart by picking options instead of memorizing
 * seaborn syntax. Generates real, readable code and inserts it as a new cell
 * — the user still sees and can edit the code, so this teaches by example
 * rather than hiding the code behind a black-box widget.
 */
@Component({
  selector: 'app-chart-helper',
  standalone: false,
  templateUrl: './chart-helper.component.html',
  styleUrl: './chart-helper.component.scss',
})
export class ChartHelperComponent {
  @Input() variables: KnownVariable[] = [];
  @Output() insert = new EventEmitter<string>();

  readonly chartTypes = CHART_LABELS;

  kind: ChartKind = 'bar';
  variable = '';
  columnX = '';
  columnY = '';

  get needsY(): boolean {
    return NEEDS_Y[this.kind];
  }

  get selectedColumns(): string[] {
    return this.variables.find((v) => v.name === this.variable)?.columns ?? [];
  }

  onVariableChange(): void {
    this.columnX = '';
    this.columnY = '';
  }

  get canInsert(): boolean {
    return !!this.variable && !!this.columnX && (!this.needsY || !!this.columnY);
  }

  insertCode(): void {
    if (!this.canInsert) {
      return;
    }
    const fn = SEABORN_FN[this.kind];
    const args = this.needsY
      ? `data=${this.variable}, x='${this.columnX}', y='${this.columnY}'`
      : `data=${this.variable}, x='${this.columnX}'`;
    const code = [
      `sns.${fn}(${args})`,
      `plt.title('${this.chartTitle()}')`,
      `plt.tight_layout()`,
    ].join('\n');
    this.insert.emit(code);
  }

  private chartTitle(): string {
    return this.needsY ? `${this.columnY} por ${this.columnX}` : `Distribución de ${this.columnX}`;
  }
}
