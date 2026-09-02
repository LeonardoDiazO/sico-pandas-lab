import { Component } from '@angular/core';

import {
  AnalysisBlock,
  AnalysisSummary,
  ColumnClassification,
  ExcelProfileColumn,
  LoadResult,
} from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

/**
 * Standalone screen for the "sin código" workflow (Epics 4-8, extended with
 * the semantic-classification + auto-analysis catalog): upload an Excel,
 * confirm/correct a suggested role per column (one click, no need to
 * already know which is "the dimension"), and get a dashboard of Pareto
 * blocks generated automatically -- no code editor anywhere on this page.
 * The manual "elige columna y tipo de gráfica" panels stay below the
 * dashboard for the one-off analysis the automatic catalog didn't cover.
 */
@Component({
  selector: 'app-no-code-home',
  standalone: false,
  templateUrl: './no-code-home.component.html',
  styleUrl: './no-code-home.component.scss',
})
export class NoCodeHomeComponent {
  banner: { text: string; ok: boolean } | null = null;
  excelProfile: { variable: string; columns: ExcelProfileColumn[] } | null = null;
  bloques: AnalysisBlock[] = [];
  resumen: AnalysisSummary | null = null;
  generatingAnalysis = false;

  constructor(private notebook: NotebookService) {}

  onLoaded(result: LoadResult): void {
    this.bloques = [];
    this.resumen = null;
    if (result.profile) {
      this.excelProfile = { variable: result.variable, columns: result.profile.columns };
    }
  }

  onClassificationConfirmed(classifications: ColumnClassification[]): void {
    this.generatingAnalysis = true;
    this.bloques = [];
    this.resumen = null;
    this.notebook.autoAnalysis(classifications).subscribe({
      next: (res) => {
        this.generatingAnalysis = false;
        this.bloques = res.data.bloques;
        this.resumen = res.data.resumen;
        if (this.bloques.length === 0) {
          this.showBanner(res.message, false);
        }
      },
      error: () => {
        this.generatingAnalysis = false;
        this.showBanner('No se pudo generar el análisis automático.', false);
      },
    });
  }

  onMessage(message: { text: string; ok: boolean }): void {
    this.banner = message;
  }

  private showBanner(text: string, ok: boolean): void {
    this.banner = { text, ok };
  }
}
