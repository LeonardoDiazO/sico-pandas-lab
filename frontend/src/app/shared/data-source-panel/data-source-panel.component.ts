import { HttpErrorResponse } from '@angular/common/http';
import { Component, EventEmitter, OnInit, Output } from '@angular/core';
import { finalize, retry, timer } from 'rxjs';

import { ApiResponse, ExcelProfile, LoadResult, SheetSummary, TableInfo } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

/**
 * Top-of-notebook panel to bring data into the session. Lists every table in
 * the sico schema (discovered dynamically, not a fixed subset) and loads any
 * of them, one at a time, as its own DataFrame. Combining tables happens in
 * pandas (pd.merge) in the user's own code — that is the skill this tool
 * exists to practice, so this panel intentionally does not build joins.
 */
@Component({
  selector: 'app-data-source-panel',
  standalone: false,
  templateUrl: './data-source-panel.component.html',
  styleUrl: './data-source-panel.component.scss',
})
export class DataSourcePanelComponent implements OnInit {
  @Output() loaded = new EventEmitter<LoadResult>();
  @Output() message = new EventEmitter<{ text: string; ok: boolean }>();

  tables: TableInfo[] = [];
  filteredTables: TableInfo[] = [];
  search = '';
  schema = 'sco';
  configured = false;
  loadingTable: string | null = null;
  excelBusy = false;
  showExcel = false;
  pendingCleanup: { variable: string; profile: ExcelProfile } | null = null;
  cleanupBusy = false;
  unusableInfo: { detail: string } | null = null;
  dragOver = false;
  // Multi-sheet workbook waiting for the user to pick sheets.
  pendingSheets: SheetSummary[] | null = null;
  chosenSheets = new Set<string>();
  sheetsBusy = false;
  lastFileName: string | null = null;

  // Columns the user unchecked on the cleanup preview screen (kept by
  // default - deselecting is opt-out, not opt-in) - sent to
  // confirm-excel-cleanup so they never end up in the bound DataFrame.
  excludedColumns = new Set<string>();

  constructor(private notebook: NotebookService) {}

  ngOnInit(): void {
    this.refreshTables();
  }

  onSearchChange(): void {
    const term = this.search.trim().toLowerCase();
    this.filteredTables = term ? this.tables.filter((t) => t.table.toLowerCase().includes(term)) : this.tables;
  }

  refreshTables(): void {
    // The RDS connection from this network is known to be intermittent (a
    // request can time out and the very next one succeeds), so one silent
    // retry before bothering the user is worth it.
    this.notebook
      .listTables()
      .pipe(retry({ count: 1, delay: () => timer(1500) }))
      .subscribe({
        next: (res) => {
          this.tables = res.data.tables;
          this.onSearchChange();
          this.schema = res.data.schema;
          this.configured = res.data.configured;
          if (!res.success) {
            this.emitMessage(res.message, false);
          }
        },
        error: () =>
          this.emitMessage(
            'No se pudo obtener la lista de tablas (la conexión a la RDS es intermitente) — usa "actualizar lista" para reintentar.',
            false,
          ),
      });
  }

  loadSingle(table: string): void {
    this.loadingTable = table;
    this.notebook
      .loadTable(table, `df_${table}`)
      .pipe(retry({ count: 1, delay: () => timer(1500) }))
      .subscribe({
        next: (res) => {
          this.loadingTable = null;
          this.emitMessage(res.message, res.success);
          if (res.success && res.data) {
            this.loaded.emit(res.data);
          }
        },
        error: () => {
          this.loadingTable = null;
          this.emitMessage('Ocurrió un error al cargar la tabla (conexión intermitente) — intenta de nuevo.', false);
        },
      });
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.excelBusy && !this.pendingCleanup) {
      this.dragOver = true;
    }
  }

  onDragLeave(event: DragEvent): void {
    // dragleave also fires when crossing into a child element - only reset
    // when the pointer actually leaves the dropzone.
    const related = event.relatedTarget as Node | null;
    if (!related || !(event.currentTarget as HTMLElement).contains(related)) {
      this.dragOver = false;
    }
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = false;
    if (this.excelBusy || this.pendingCleanup) {
      return;
    }
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.uploadFile(file);
    }
  }

  onExcel(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    // Cleared right away (not only on success): previously an upload error
    // skipped `complete`, so picking the same file again fired no change
    // event and nothing happened.
    input.value = '';
    if (file) {
      this.uploadFile(file);
    }
  }

  private uploadFile(file: File): void {
    if (!/\.(xlsx|xls)$/i.test(file.name)) {
      this.emitMessage(`"${file.name}" no es un Excel. Sube un archivo .xlsx o .xls.`, false);
      return;
    }
    this.lastFileName = file.name;
    this.excelBusy = true;
    this.pendingCleanup = null;
    this.pendingSheets = null;
    this.unusableInfo = null;
    this.excludedColumns = new Set<string>();
    this.notebook
      .uploadExcel(file, 'df')
      .pipe(finalize(() => (this.excelBusy = false)))
      .subscribe({
      next: (res) => this.handleLoadResponse(res),
      error: (err: HttpErrorResponse) => {
        const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
        this.emitMessage(backendMessage ?? 'No se pudo subir el Excel. Revisa tu conexión e inténtalo otra vez.', false);
      },
    });
  }

  // Shared by /upload-excel and /select-sheets: same verdict handling.
  private handleLoadResponse(res: ApiResponse<LoadResult>): void {
    if (!res.success || !res.data) {
      this.emitMessage(res.message, false);
      return;
    }
    if (res.data.needsSheetSelection && res.data.sheets?.length) {
      // Decisión #4: the user chooses which sheets to stack (column "Hoja").
      this.pendingSheets = res.data.sheets;
      this.chosenSheets = new Set(res.data.sheets.filter((s) => s.usable).map((s) => s.name));
      return;
    }
    this.pendingSheets = null;
    const profile = res.data.profile;
    if (!profile || profile.verdict === 'usable') {
      // Ya limpio (o una respuesta sin profile, ej. carga de tabla): comportamiento de siempre.
      this.emitMessage(res.message, true);
      this.loaded.emit(res.data);
    } else if (profile.verdict === 'usable_con_limpieza') {
      // No se emite `loaded` todavía -- el DataFrame no está bindeado hasta confirmar (Story 4.2).
      this.pendingCleanup = { variable: res.data.variable, profile };
      this.excludedColumns = new Set<string>();
    } else {
      // no_usable: bloque dedicado (UX-DR1), no el banner genérico de error.
      this.unusableInfo = { detail: profile.detail };
    }
  }

  toggleSheet(name: string): void {
    if (this.chosenSheets.has(name)) {
      this.chosenSheets.delete(name);
    } else {
      this.chosenSheets.add(name);
    }
    this.chosenSheets = new Set(this.chosenSheets);
  }

  confirmSheets(): void {
    if (!this.pendingSheets || this.chosenSheets.size === 0 || this.sheetsBusy) {
      return;
    }
    // Keep the workbook's own sheet order.
    const chosen = this.pendingSheets.map((s) => s.name).filter((n) => this.chosenSheets.has(n));
    this.sheetsBusy = true;
    this.notebook
      .selectSheets(chosen)
      .pipe(finalize(() => (this.sheetsBusy = false)))
      .subscribe({
        next: (res) => this.handleLoadResponse(res),
        error: (err: HttpErrorResponse) => {
          const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
          this.emitMessage(backendMessage ?? 'No se pudieron combinar las hojas. Intenta de nuevo.', false);
        },
      });
  }

  toggleExcludeColumn(name: string): void {
    if (this.excludedColumns.has(name)) {
      this.excludedColumns.delete(name);
    } else {
      this.excludedColumns.add(name);
    }
  }

  get keptColumnCount(): number {
    return (this.pendingCleanup?.profile.columns.length ?? 0) - this.excludedColumns.size;
  }

  confirmCleanup(): void {
    if (!this.pendingCleanup || this.keptColumnCount < 1) {
      return;
    }
    this.cleanupBusy = true;
    this.notebook.confirmExcelCleanup(Array.from(this.excludedColumns)).subscribe({
      next: (res) => {
        this.cleanupBusy = false;
        this.pendingCleanup = null;
        this.excludedColumns = new Set<string>();
        this.emitMessage(res.message, res.success);
        if (res.success && res.data) {
          this.loaded.emit(res.data);
        }
      },
      error: (err: HttpErrorResponse) => {
        // The pending upload survives a rejected confirm (e.g. "excluiste
        // todas las columnas") on the backend - surface its specific
        // message so the user knows what to fix, same pattern as
        // no-code-chart's generateChart() error handling.
        this.cleanupBusy = false;
        const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
        this.emitMessage(backendMessage ?? 'Ocurrió un error al confirmar la limpieza.', false);
      },
    });
  }

  cancelCleanup(): void {
    if (!this.pendingCleanup) {
      return;
    }
    this.cleanupBusy = true;
    this.notebook.cancelExcelCleanup().subscribe({
      next: () => {
        this.cleanupBusy = false;
        this.pendingCleanup = null;
        this.excludedColumns = new Set<string>();
      },
      error: () => {
        // Keep pendingCleanup as-is: the request may not have reached the
        // backend, so pretending cancellation succeeded here would let the
        // frontend and backend state silently diverge (see confirmCleanup's
        // error handling for the same reasoning).
        this.cleanupBusy = false;
        this.emitMessage('No se pudo cancelar la carga. Intenta de nuevo.', false);
      },
    });
  }

  /** Called by the parent on session restart, which discards any pending
   * upload server-side -- this clears the matching local UI state so a
   * stale "Confirmar y continuar" button can't linger after a restart. */
  resetUploadState(): void {
    this.pendingCleanup = null;
    this.unusableInfo = null;
    this.cleanupBusy = false;
    this.excelBusy = false;
    this.excludedColumns = new Set<string>();
  }

  private emitMessage(text: string, ok: boolean): void {
    this.message.emit({ text, ok });
  }
}
