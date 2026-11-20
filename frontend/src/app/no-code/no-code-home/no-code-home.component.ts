import { Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { Subscription } from 'rxjs';

import {
  AnalysisBlock,
  AnalysisSummary,
  ColumnClassification,
  ColumnFilter,
  DataQuality,
  ExcelProfileColumn,
  LoadResult,
} from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

/**
 * Standalone screen for the "sin código" workflow: upload an Excel,
 * confirm/correct a suggested role per column, and get an explorable
 * dashboard of Pareto blocks generated automatically - no code editor on
 * this page. The manual "elige columna y tipo de gráfica" panels stay below
 * for the one-off analysis the automatic catalog didn't cover.
 */
@Component({
  selector: 'app-no-code-home',
  standalone: false,
  templateUrl: './no-code-home.component.html',
  styleUrl: './no-code-home.component.scss',
})
export class NoCodeHomeComponent implements OnDestroy {
  @ViewChild('resultsAnchor') private resultsAnchor?: ElementRef<HTMLElement>;

  banner: { text: string; ok: boolean } | null = null;
  excelProfile: { variable: string; columns: ExcelProfileColumn[]; rows: number } | null = null;
  fileLabel: string | null = null;
  quality: DataQuality | null = null;
  sheetsUsed: string[] = [];
  bloques: AnalysisBlock[] = [];
  resumen: AnalysisSummary | null = null;
  generatingAnalysis = false;
  analysisError: string | null = null;
  // Only the latest request may write results: re-confirming (or uploading a
  // new file) while one is in flight used to let the older, slower response
  // overwrite the newer one.
  private analysisSub?: Subscription;
  private lastClassifications: ColumnClassification[] | null = null;

  constructor(private notebook: NotebookService) {}

  ngOnDestroy(): void {
    this.analysisSub?.unsubscribe();
  }

  get currentStep(): 1 | 2 | 3 {
    if (!this.excelProfile) {
      return 1;
    }
    return this.bloques.length > 0 || this.generatingAnalysis ? 3 : 2;
  }

  onLoaded(result: LoadResult): void {
    this.analysisSub?.unsubscribe();
    this.generatingAnalysis = false;
    this.analysisError = null;
    this.bloques = [];
    this.resumen = null;
    this.lastClassifications = null;
    this.quality = result.profile?.quality ?? null;
    this.sheetsUsed = result.sheetsUsed ?? [];
    if (result.profile) {
      this.excelProfile = { variable: result.variable, columns: result.profile.columns, rows: result.rows };
      this.fileLabel = `${result.rows.toLocaleString('es-CO')} filas · ${result.profile.columns.length} columnas`;
    }
  }

  onClassificationConfirmed(classifications: ColumnClassification[]): void {
    this.runAnalysis(classifications, []);
  }

  // Cross-filter from the dashboard: same confirmed classification, new filters.
  onFiltersChange(filters: ColumnFilter[]): void {
    if (this.lastClassifications) {
      this.runAnalysis(this.lastClassifications, filters, false);
    }
  }

  get qualityIssues(): { label: string; detail: string }[] {
    const q = this.quality;
    if (!q) {
      return [];
    }
    const issues: { label: string; detail: string }[] = [];
    const blanks = q.columns.filter((c) => c.nullCount > 0).sort((a, b) => b.nullRatio - a.nullRatio);
    if (blanks.length) {
      issues.push({
        label: `${blanks.length} ${blanks.length === 1 ? 'columna tiene' : 'columnas tienen'} celdas vacías`,
        detail: blanks
          .slice(0, 4)
          .map((c) => `${c.name} (${Math.round(c.nullRatio * 100)}%)`)
          .join(', ') + (blanks.length > 4 ? '…' : ''),
      });
    }
    if (q.duplicateRows > 0) {
      issues.push({
        label: `${q.duplicateRows} ${q.duplicateRows === 1 ? 'fila repetida' : 'filas repetidas'}`,
        detail: 'Filas idénticas en todas sus columnas: revisa si son registros duplicados antes de sumar.',
      });
    }
    const negatives = q.columns.filter((c) => (c.negativeCount ?? 0) > 0);
    if (negatives.length) {
      issues.push({
        label: `Valores negativos en ${negatives.map((c) => c.name).join(', ')}`,
        detail: 'Suelen ser notas crédito o devoluciones: el tablero trabaja con el neto de cada grupo.',
      });
    }
    return issues;
  }

  get qualityCleanups(): string[] {
    const q = this.quality;
    const out: string[] = [];
    if (q?.totalsRowsRemoved) {
      out.push(`${q.totalsRowsRemoved} ${q.totalsRowsRemoved === 1 ? 'fila de totales quitada' : 'filas de totales quitadas'} (para no sumar dos veces)`);
    }
    if (q?.emptyRowsRemoved) {
      out.push(`${q.emptyRowsRemoved} ${q.emptyRowsRemoved === 1 ? 'fila vacía quitada' : 'filas vacías quitadas'}`);
    }
    return out;
  }

  private runAnalysis(classifications: ColumnClassification[], filters: ColumnFilter[], scroll = true): void {
    this.lastClassifications = classifications;
    this.analysisSub?.unsubscribe();
    this.generatingAnalysis = true;
    this.analysisError = null;
    this.banner = null;
    if (scroll) {
      this.bloques = [];
      this.resumen = null;
      this.scrollToResults();
    }
    this.analysisSub = this.notebook.autoAnalysis(classifications, {}, filters).subscribe({
      next: (res) => {
        this.generatingAnalysis = false;
        this.bloques = res.data.bloques;
        this.resumen = res.data.resumen;
        if (this.bloques.length === 0) {
          this.analysisError = res.message;
        }
      },
      error: () => {
        this.generatingAnalysis = false;
        this.analysisError = 'No se pudo generar el análisis automático. Revisa tu conexión e inténtalo otra vez.';
      },
    });
  }

  retryAnalysis(): void {
    if (this.lastClassifications) {
      this.onClassificationConfirmed(this.lastClassifications);
    }
  }

  onMessage(message: { text: string; ok: boolean }): void {
    this.banner = message;
  }

  dismissBanner(): void {
    this.banner = null;
  }

  private scrollToResults(): void {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    // After the step-3 container renders.
    setTimeout(() =>
      this.resultsAnchor?.nativeElement.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }),
    );
  }
}
