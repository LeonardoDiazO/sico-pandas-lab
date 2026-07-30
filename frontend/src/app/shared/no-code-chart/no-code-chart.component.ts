import { HttpErrorResponse } from '@angular/common/http';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { CardinalityWarning, ChartInterpretation, ChartResult, ExcelProfileColumn } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

export interface ExcelProfileState {
  variable: string;
  columns: ExcelProfileColumn[];
}

const GROUPABLE_TYPES: ExcelProfileColumn['type'][] = ['categorica', 'fecha'];

export type ChartKind =
  | 'torta'
  | 'barras'
  | 'linea'
  | 'histograma'
  | 'area'
  | 'boxplot'
  | 'heatmap'
  | 'dispersion';

interface ChartTypeOption {
  value: ChartKind;
  label: string;
}

const CHART_TYPE_LABELS: Record<ChartKind, string> = {
  torta: 'Torta',
  barras: 'Barras',
  linea: 'Línea',
  histograma: 'Histograma',
  area: 'Área',
  boxplot: 'Caja y bigotes',
  heatmap: 'Mapa de calor',
  dispersion: 'Dispersión',
};

// User feedback ("sería bueno explicar antes"): shown right under the chart
// type selector so the user knows what columns it needs BEFORE clicking
// "Generar" and hitting a backend validation error - same facts documented
// in chart_builder.py's build_chart_code() docstring, kept in sync manually
// (no shared module between the Python backend and this TypeScript frontend).
const CHART_TYPE_HINTS: Record<ChartKind, string> = {
  torta: 'Necesita 1 o más columnas de categoría/fecha para agrupar (columna de valor opcional). Ideal con pocas categorías — arriba de ~15 se agrupan como "Otros".',
  barras: 'Necesita 1 o más columnas de categoría/fecha para agrupar (columna de valor opcional). Mismo límite de ~15 categorías legibles que torta.',
  linea: 'Necesita exactamente 1 columna de fecha (columna de valor opcional).',
  histograma: 'Necesita 1 columna numérica — ignora cualquier columna de agrupación.',
  area: 'Necesita exactamente 1 columna de fecha + 1 columna numérica (obligatoria).',
  boxplot: 'Necesita exactamente 1 columna de categoría + 1 columna numérica (obligatoria).',
  heatmap: 'Necesita exactamente 2 columnas de categoría + 1 columna numérica (obligatoria).',
  dispersion: 'Necesita 2 columnas numéricas distintas (eje X y eje Y) — elígelas abajo.',
};

/**
 * Story 5.1: lets the user pick a column to group/plot by, no Python
 * involved anywhere in this flow (distinct from the pre-existing
 * ChartHelperComponent, which generates code for the user to run).
 * Story 5.2: adds the chart-type selector (UX-DR3) - torta/barras for a
 * categorica grouping column, linea for fecha, histograma whenever a numeric
 * value column is picked (a histogram plots ONE numeric column's own
 * distribution, independent of whatever grouping column is selected - see
 * GUIA_PRACTICA_FACTURAS_MATECOL.md's `df['neto'].plot.hist()` example).
 * Story 5.3 adds the "generate" action - selectedChartType has no consumer yet.
 */
@Component({
  selector: 'app-no-code-chart',
  standalone: false,
  templateUrl: './no-code-chart.component.html',
  styleUrl: './no-code-chart.component.scss',
})
export class NoCodeChartComponent implements OnChanges {
  @Input() profile: ExcelProfileState | null = null;

  // Story 7.2: multiple columns can be marked at once (checkboxes) to group
  // by their combination - see chartTypeOptions for the compatibility rule.
  selectedColumns: string[] = [];
  selectedValueColumn: string | null = null;
  selectedChartType: ChartKind | null = null;
  // Dispersión is the one chart type that needs two NUMERIC columns (X, Y)
  // instead of the categorica/fecha checkbox + single numeric value model
  // every other type uses - own dedicated selects rather than repurposing
  // selectedColumns/selectedValueColumn's meaning per chart type.
  selectedScatterX: string | null = null;
  selectedScatterY: string | null = null;
  generating = false;
  chartResult: ChartResult | null = null;
  cardinalityWarning: CardinalityWarning | null = null;

  // Story 6.1: natural-language assistant - only fills the selectors above,
  // never generates or executes anything itself (NFR10). The user still
  // presses "Generar gráfica" themselves after reviewing the filled-in
  // selection - see Dev Notes in the story file for why.
  naturalLanguageQuestion = '';
  interpreting = false;
  interpretationReason: string | null = null;

  constructor(private notebook: NotebookService) {}

  get groupableColumns(): ExcelProfileColumn[] {
    return this.profile?.columns.filter((c) => GROUPABLE_TYPES.includes(c.type)) ?? [];
  }

  get numericColumns(): ExcelProfileColumn[] {
    return this.profile?.columns.filter((c) => c.type === 'numerica') ?? [];
  }

  get chartTypeHint(): string | null {
    return this.selectedChartType ? CHART_TYPE_HINTS[this.selectedChartType] : null;
  }

  private static readonly ALL_CHART_KINDS: ChartKind[] = [
    'torta',
    'barras',
    'linea',
    'histograma',
    'area',
    'boxplot',
    'heatmap',
    'dispersion',
  ];

  get chartTypeOptions(): ChartTypeOption[] {
    // By user request: the user picks whichever chart type they want, no
    // pre-filtering by column-type compatibility (e.g. línea with a
    // non-fecha column) - the backend already validates and returns a clear
    // error message for combinations that don't make sense (routes.py's
    // generate_chart), so hiding options here was a stricter, redundant
    // rule the backend itself doesn't enforce. Only gate on "the user has
    // selected *something*" so the initial empty state still nudges them.
    if (this.selectedColumns.length === 0 && !this.selectedValueColumn) {
      return [];
    }
    return NoCodeChartComponent.ALL_CHART_KINDS.map((value) => ({ value, label: CHART_TYPE_LABELS[value] }));
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['profile']) {
      const groupable = new Set(this.groupableColumns.map((c) => c.name));
      this.selectedColumns = this.selectedColumns.filter((name) => groupable.has(name));
      // Reverted: auto-picking groupableColumns[0] regardless of type broke
      // línea whenever the first groupable column in the file wasn't a
      // "fecha" column (e.g. a junk placeholder column appearing before the
      // real date column) - the user would get línea silently trying to
      // parse a non-date column. The value-column default below is what
      // actually fixed the reported bug (forgetting to pick a value column)
      // without this type-mismatch risk, so grouping-column selection stays
      // manual.
      if (!this.numericColumns.some((c) => c.name === this.selectedValueColumn)) {
        // Smart default (user feedback, real bug: a "línea"/"torta"/"barras"
        // chart generated with no value column silently switches to
        // "count rows" mode, which reads as a completely different,
        // confusing result - e.g. a small y-axis of row counts instead of
        // the expected sum of amounts). Auto-picking the first numeric
        // column when a fresh profile loads means the user has to actively
        // clear it (select "Ninguna") to get count-mode, instead of having
        // to remember to opt IN to a sum every time.
        this.selectedValueColumn = this.numericColumns[0]?.name ?? null;
      }
      // No smart default for X/Y (dispersión is opt-in, unlike the other
      // types) - just drop a selection that no longer exists on the new
      // profile, same reasoning as selectedColumns' groupable.has() filter.
      if (!this.numericColumns.some((c) => c.name === this.selectedScatterX)) {
        this.selectedScatterX = null;
      }
      if (!this.numericColumns.some((c) => c.name === this.selectedScatterY)) {
        this.selectedScatterY = null;
      }
    }
    this.revalidateChartType();
  }

  toggleColumn(name: string): void {
    const index = this.selectedColumns.indexOf(name);
    if (index === -1) {
      this.selectedColumns = [...this.selectedColumns, name];
    } else {
      this.selectedColumns = this.selectedColumns.filter((c) => c !== name);
    }
    this.revalidateChartType();
  }

  onValueColumnChange(): void {
    this.revalidateChartType();
  }

  onChartTypeChange(): void {
    this.clearResult();
  }

  get canGenerate(): boolean {
    // Also blocked while the assistant is thinking: it may overwrite
    // selectedColumns/selectedValueColumn/selectedChartType any moment via
    // applyInterpretation(), so generating from a selection that could be
    // replaced out from under the user is unsafe - see askAssistant().
    if (!this.profile || !this.selectedChartType || this.generating || this.interpreting) {
      return false;
    }
    if (this.selectedChartType === 'histograma') {
      return !!this.selectedValueColumn;
    }
    if (this.selectedChartType === 'dispersion') {
      return (
        !!this.selectedScatterX && !!this.selectedScatterY && this.selectedScatterX !== this.selectedScatterY
      );
    }
    return this.selectedColumns.length > 0;
  }

  generateChart(force = false): void {
    if (!this.profile || !this.selectedChartType || (!force && !this.canGenerate)) {
      return;
    }
    this.generating = true;
    this.clearResult();
    const isScatter = this.selectedChartType === 'dispersion';
    const columns = isScatter ? [this.selectedScatterX!, this.selectedScatterY!] : this.selectedColumns;
    const valueColumn = isScatter ? null : this.selectedValueColumn;
    this.notebook
      .generateChart(this.profile.variable, columns, valueColumn, this.selectedChartType, force)
      .subscribe({
        next: (res) => {
          this.generating = false;
          if (res.data?.needsConfirmation) {
            this.cardinalityWarning = res.data.cardinalityWarning;
          } else {
            this.chartResult = res.data ?? null;
          }
        },
        error: (err: HttpErrorResponse) => {
          this.generating = false;
          // A 4xx/5xx from our own backend carries the real ApiResponse body
          // (message/success/...) in err.error -- surface that instead of a
          // generic "can't reach the server", which would otherwise hide a
          // real validation message (e.g. client/server rule drift).
          const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
          this.chartResult = {
            stdout: null,
            result_html: null,
            result_text: null,
            image_base64: null,
            error: {
              type: 'RedError',
              message: backendMessage ?? 'No se pudo contactar el servidor.',
              traceback: '',
            },
            needsConfirmation: false,
            cardinalityWarning: null,
            explanation: null,
          };
        },
      });
  }

  generateAnyway(): void {
    this.generateChart(true);
  }

  askAssistant(): void {
    if (!this.profile || !this.naturalLanguageQuestion.trim() || this.interpreting) {
      return;
    }
    this.interpreting = true;
    this.interpretationReason = null;
    this.notebook.interpretChartRequest(this.naturalLanguageQuestion, this.profile.columns).subscribe({
      next: (res) => {
        this.interpreting = false;
        this.applyInterpretation(res.data ?? null);
      },
      error: (err: HttpErrorResponse) => {
        this.interpreting = false;
        const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
        this.interpretationReason =
          backendMessage ?? 'No se pudo contactar el asistente. Usa los selectores manuales.';
      },
    });
  }

  private applyInterpretation(interpretation: ChartInterpretation | null): void {
    if (!interpretation || !interpretation.resolved) {
      this.interpretationReason =
        interpretation?.reason ?? 'No pude resolver esa pregunta. Usa los selectores manuales.';
      return;
    }
    // Never trust the backend answer blindly here either (third layer of
    // defense - see the story's Dev Notes) - only apply values that are
    // still valid against the current selector options. The assistant
    // (Story 6.1) still resolves to a single column - wrap it as a
    // one-element list for the checkbox-based selection (Story 7.2 AC7).
    this.selectedColumns =
      interpretation.column && this.groupableColumns.some((c) => c.name === interpretation.column)
        ? [interpretation.column]
        : [];
    this.selectedValueColumn = this.numericColumns.some((c) => c.name === interpretation.valueColumn)
      ? interpretation.valueColumn
      : null;
    this.revalidateChartType();
    if (interpretation.chartType && this.chartTypeOptions.some((o) => o.value === interpretation.chartType)) {
      this.selectedChartType = interpretation.chartType;
    }
    this.interpretationReason = null;
  }

  private revalidateChartType(): void {
    this.clearResult();
    if (!this.chartTypeOptions.some((o) => o.value === this.selectedChartType)) {
      this.selectedChartType = null;
    }
  }

  private clearResult(): void {
    this.chartResult = null;
    this.cardinalityWarning = null;
  }
}
