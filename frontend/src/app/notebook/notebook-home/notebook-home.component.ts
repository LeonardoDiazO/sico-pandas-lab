import { AfterViewInit, Component, HostListener, OnDestroy, ViewChild } from '@angular/core';

import { NotebookDraftService } from '../../core/notebook-draft.service';
import { Snippet, SnippetsService } from '../../core/snippets.service';
import { TourService } from '../../core/tour.service';
import { CellResult, ExcelProfileColumn, LoadResult } from '../../models/api.models';
import { DataSourcePanelComponent } from '../../shared/data-source-panel/data-source-panel.component';
import { KnownVariable } from '../../shared/chart-helper/chart-helper.component';
import { SnippetSaveRequest } from '../../shared/code-cell/code-cell.component';
import { NotebookService } from '../services/notebook.service';
import { NOTEBOOK_TOUR_STEPS } from './notebook-tour-steps';

interface Cell {
  code: string;
  result: CellResult | null;
  running: boolean;
}

const STARTER = `# 1) Carga una o más tablas desde el panel de arriba (cada una queda como df_<tabla>)
# 2) Explora lo que trajiste, por ejemplo:
# df_02_item.head()
# df_02_item.describe()

# 3) Para combinar dos tablas, usa pd.merge() -- así se hace un "join" en pandas:
# pd.merge(df_02_movimiento, df_02_item, left_on='mov_item', right_on='item_codigo')

# 4) Agrupa y grafica con lo que ya conoces de pandas:
# df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum().plot(kind='bar')

# Ejecuta esta celda (▶ o Ctrl/Cmd+Enter) para empezar:
import pandas as pd
print('Listo. Carga una tabla arriba y reemplaza este texto por tu análisis.')`;

@Component({
  selector: 'app-notebook-home',
  standalone: false,
  templateUrl: './notebook-home.component.html',
  styleUrl: './notebook-home.component.scss',
})
export class NotebookHomeComponent implements AfterViewInit, OnDestroy {
  @ViewChild(DataSourcePanelComponent) dataSourcePanel?: DataSourcePanelComponent;

  cells: Cell[] = [{ code: STARTER, result: null, running: false }];
  banner: { text: string; ok: boolean } | null = null;
  knownVariables: KnownVariable[] = [];
  snippets: Snippet[] = [];
  restoredDraft = false;
  /** The most recently profiled Excel (Epic 4) - null until one is loaded.
   * Table loads from sico never carry `profile` (no profiling there), so
   * this intentionally only updates on Excel loads, not on every `loaded`
   * event - see Story 5.1 Dev Notes for why. */
  excelProfile: { variable: string; columns: ExcelProfileColumn[] } | null = null;

  constructor(
    private notebook: NotebookService,
    private tour: TourService,
    private draftService: NotebookDraftService,
    private snippetsService: SnippetsService,
  ) {
    const draft = this.draftService.load();
    const isTrivial = !draft || (draft.length === 1 && draft[0] === STARTER);
    if (draft && !isTrivial) {
      this.cells = draft.map((code) => ({ code, result: null, running: false }));
      this.restoredDraft = true;
    }
    this.snippets = this.snippetsService.list();
  }

  ngAfterViewInit(): void {
    setTimeout(() => this.tour.startIfFirstVisit('notebook', NOTEBOOK_TOUR_STEPS));
  }

  // Doubles as both the Angular destroy hook (leaving via in-app navigation)
  // and the raw window event (closing/refreshing the tab) -- either one
  // needs to capture the latest draft, so one method serves both triggers.
  @HostListener('window:beforeunload')
  ngOnDestroy(): void {
    this.saveDraft();
  }

  startTour(): void {
    this.tour.start('notebook', NOTEBOOK_TOUR_STEPS);
  }

  addCell(): void {
    this.cells.push({ code: '', result: null, running: false });
  }

  removeCell(index: number): void {
    this.cells.splice(index, 1);
    if (this.cells.length === 0) {
      this.addCell();
    }
  }

  runCell(index: number, code: string): void {
    const cell = this.cells[index];
    cell.code = code;
    cell.running = true;
    this.notebook.execute(code).subscribe({
      next: (res) => {
        cell.result = res.data;
        cell.running = false;
      },
      error: () => {
        cell.running = false;
        cell.result = {
          stdout: null,
          result_html: null,
          result_text: null,
          image_base64: null,
          error: { type: 'RedError', message: 'No se pudo contactar el servidor.', traceback: '' },
        };
      },
    });
  }

  restart(): void {
    this.notebook.restart().subscribe({
      next: (res) => {
        this.cells = [{ code: STARTER, result: null, running: false }];
        this.knownVariables = [];
        this.draftService.clear();
        this.restoredDraft = false;
        this.showBanner(res.message, true);
        // Backend restart() also discards any pending Excel-cleanup upload
        // for this session -- clear the matching local UI state so a stale
        // "Confirmar y continuar" button can't linger after a restart.
        this.dataSourcePanel?.resetUploadState();
        this.excelProfile = null;
      },
      error: () => this.showBanner('No se pudo reiniciar la sesión.', false),
    });
  }

  discardDraft(): void {
    this.cells = [{ code: STARTER, result: null, running: false }];
    this.draftService.clear();
    this.restoredDraft = false;
  }

  onLoaded(result: LoadResult): void {
    // Drop a ready-to-run cell that shows the freshly loaded DataFrame.
    this.cells.push({ code: `${result.variable}.head()`, result: null, running: false });
    this.rememberVariable(result.variable, result.columns);
    if (result.profile) {
      this.excelProfile = { variable: result.variable, columns: result.profile.columns };
    }
  }

  insertCode(code: string): void {
    this.cells.push({ code, result: null, running: false });
  }

  onSaveSnippet(request: SnippetSaveRequest): void {
    this.snippets = this.snippetsService.save(request.name, request.note, request.code);
    this.showBanner(`Guardado: "${request.name}"`, true);
  }

  onRemoveSnippet(id: string): void {
    this.snippets = this.snippetsService.remove(id);
  }

  onMessage(message: { text: string; ok: boolean }): void {
    this.showBanner(message.text, message.ok);
  }

  private rememberVariable(name: string, columns: string[]): void {
    const existing = this.knownVariables.find((v) => v.name === name);
    if (existing) {
      existing.columns = columns;
    } else {
      this.knownVariables = [...this.knownVariables, { name, columns }];
    }
  }

  private showBanner(text: string, ok: boolean): void {
    this.banner = { text, ok };
  }

  private saveDraft(): void {
    this.draftService.save(this.cells.map((c) => c.code));
  }
}
