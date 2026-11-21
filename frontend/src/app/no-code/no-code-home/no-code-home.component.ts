import { Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';

export type WizardStep = 1 | 2 | 3 | 4;

interface WizardStepInfo {
  n: WizardStep;
  title: string;
  hint: string;
}
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
import { ToastService } from '../../core/toast.service';
import { NotebookService } from '../../notebook/services/notebook.service';
import { ColumnClassificationComponent } from '../../shared/column-classification/column-classification.component';

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
  @ViewChild('wizardTop') private wizardTop?: ElementRef<HTMLElement>;
  @ViewChild(ColumnClassificationComponent) private classification?: ColumnClassificationComponent;

  // Step-by-step flow (user feedback: scrolling down a long page to reach the
  // next step was uncomfortable) - one step on screen at a time, moved with
  // Anterior/Siguiente or the clickable step indicator. Steps stay mounted
  // while hidden, so nothing done in a step is lost when moving between them.
  readonly steps: WizardStepInfo[] = [
    { n: 1, title: 'Sube tu archivo', hint: 'Excel .xlsx o .xls' },
    { n: 2, title: 'Confirma las columnas', hint: 'Qué es cada una' },
    { n: 3, title: 'Explora el tablero', hint: 'Gráficas y hallazgos' },
    { n: 4, title: 'Análisis a mano', hint: 'Opcional' },
  ];
  activeStep: WizardStep = 1;
  // Slide direction of the last move (for the transition).
  direction: 'forward' | 'back' = 'forward';

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

  constructor(
    private notebook: NotebookService,
    private toast: ToastService,
  ) {}

  ngOnDestroy(): void {
    this.analysisSub?.unsubscribe();
  }

  isDone(n: WizardStep): boolean {
    switch (n) {
      case 1:
        return !!this.excelProfile;
      case 2:
        return this.bloques.length > 0;
      case 3:
        return this.bloques.length > 0;
      default:
        return false;
    }
  }

  canGoTo(n: WizardStep): boolean {
    switch (n) {
      case 1:
        return true;
      case 2:
      case 4:
        return !!this.excelProfile;
      case 3:
        return this.generatingAnalysis || this.bloques.length > 0 || !!this.analysisError;
    }
  }

  goTo(n: WizardStep): void {
    if (!this.canGoTo(n) || n === this.activeStep) {
      return;
    }
    this.direction = n > this.activeStep ? 'forward' : 'back';
    this.activeStep = n;
    this.bringWizardIntoView();
  }

  get nextStep(): WizardStep | null {
    return this.activeStep < 4 ? ((this.activeStep + 1) as WizardStep) : null;
  }

  get prevStep(): WizardStep | null {
    return this.activeStep > 1 ? ((this.activeStep - 1) as WizardStep) : null;
  }

  // Why "Siguiente" is disabled, said in plain words next to it.
  get nextBlockedReason(): string | null {
    const next = this.nextStep;
    if (!next || this.canGoTo(next)) {
      return null;
    }
    if (this.activeStep === 1) {
      return 'Sube un archivo para continuar.';
    }
    if (this.activeStep === 2) {
      return this.classification?.missing ?? null;
    }
    return null;
  }

  // Step 2's primary action lives in the fixed bar too: with many columns
  // the "Generar tablero" button at the end of the list was a scroll away.
  get step2Action(): 'generate' | 'update' | 'next' | null {
    if (this.activeStep !== 2 || !this.classification) {
      return null;
    }
    if (this.classification.dirty) {
      return 'update';
    }
    return this.bloques.length > 0 ? 'next' : 'generate';
  }

  get step2ActionDisabled(): boolean {
    const c = this.classification;
    return !c || c.loading || !c.classifications.length || !!c.missing || this.generatingAnalysis;
  }

  runStep2Action(): void {
    if (this.step2Action === 'next') {
      this.goTo(3);
    } else {
      this.classification?.confirm();
    }
  }

  get classificationMissing(): string | null {
    return this.classification?.missing ?? null;
  }

  get nextLabel(): string {
    const next = this.nextStep;
    return next ? `Siguiente: ${this.steps[next - 1].title.toLowerCase()}` : '';
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
    if (scroll) {
      this.bloques = [];
      this.resumen = null;
      // Generating moves straight to the dashboard step (its skeleton shows progress).
      this.direction = 'forward';
      this.activeStep = 3;
      this.bringWizardIntoView();
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
    this.toast.show(message.text, message.ok);
  }

  // Only scrolls when the step indicator is above the viewport (e.g. after
  // reading a long dashboard) - never a jump when it is already visible.
  private bringWizardIntoView(): void {
    const el = this.wizardTop?.nativeElement;
    if (!el || typeof window === 'undefined') {
      return;
    }
    if (el.getBoundingClientRect().top < 0) {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    }
  }
}
