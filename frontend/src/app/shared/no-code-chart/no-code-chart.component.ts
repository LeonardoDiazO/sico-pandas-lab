import { HttpErrorResponse } from '@angular/common/http';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { CardinalityWarning, ChartInterpretation, ChartResult, ExcelProfileColumn } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

export interface ExcelProfileState {
  variable: string;
  columns: ExcelProfileColumn[];
}

const GROUPABLE_TYPES: ExcelProfileColumn['type'][] = ['categorica', 'fecha'];

export type ChartKind = 'torta' | 'barras' | 'linea' | 'histograma';

interface ChartTypeOption {
  value: ChartKind;
  label: string;
}

const CHART_TYPE_LABELS: Record<ChartKind, string> = {
  torta: 'Torta',
  barras: 'Barras',
  linea: 'Línea',
  histograma: 'Histograma',
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

  selectedColumn: string | null = null;
  selectedValueColumn: string | null = null;
  selectedChartType: ChartKind | null = null;
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

  get chartTypeOptions(): ChartTypeOption[] {
    const kinds: ChartKind[] = [];
    const column = this.profile?.columns.find((c) => c.name === this.selectedColumn);
    if (column?.type === 'categorica') {
      kinds.push('torta', 'barras');
    } else if (column?.type === 'fecha') {
      kinds.push('linea');
    }
    if (this.selectedValueColumn) {
      kinds.push('histograma');
    }
    return kinds.map((value) => ({ value, label: CHART_TYPE_LABELS[value] }));
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['profile']) {
      if (!this.groupableColumns.some((c) => c.name === this.selectedColumn)) {
        this.selectedColumn = null;
      }
      if (!this.numericColumns.some((c) => c.name === this.selectedValueColumn)) {
        this.selectedValueColumn = null;
      }
    }
    this.revalidateChartType();
  }

  onColumnChange(): void {
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
    // selectedColumn/selectedValueColumn/selectedChartType any moment via
    // applyInterpretation(), so generating from a selection that could be
    // replaced out from under the user is unsafe - see askAssistant().
    if (!this.profile || !this.selectedChartType || this.generating || this.interpreting) {
      return false;
    }
    if (this.selectedChartType === 'histograma') {
      return !!this.selectedValueColumn;
    }
    return !!this.selectedColumn;
  }

  generateChart(force = false): void {
    if (!this.profile || !this.selectedChartType || (!force && !this.canGenerate)) {
      return;
    }
    this.generating = true;
    this.clearResult();
    this.notebook
      .generateChart(
        this.profile.variable,
        this.selectedColumn,
        this.selectedValueColumn,
        this.selectedChartType,
        force,
      )
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
    // still valid against the current selector options.
    this.selectedColumn = this.groupableColumns.some((c) => c.name === interpretation.column)
      ? interpretation.column
      : null;
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
