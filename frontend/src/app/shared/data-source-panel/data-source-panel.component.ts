import { Component, EventEmitter, OnInit, Output } from '@angular/core';
import { retry, timer } from 'rxjs';

import { ExcelProfile, LoadResult, TableInfo } from '../../models/api.models';
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

  onExcel(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    this.excelBusy = true;
    this.pendingCleanup = null;
    this.unusableInfo = null;
    this.notebook.uploadExcel(file, 'df').subscribe({
      next: (res) => {
        this.excelBusy = false;
        if (!res.success || !res.data) {
          this.emitMessage(res.message, false);
          return;
        }
        const profile = res.data.profile;
        if (!profile || profile.verdict === 'usable') {
          // Ya limpio (o una respuesta sin profile, ej. carga de tabla): comportamiento de siempre.
          this.emitMessage(res.message, true);
          this.loaded.emit(res.data);
        } else if (profile.verdict === 'usable_con_limpieza') {
          // No se emite `loaded` todavía -- el DataFrame no está bindeado hasta confirmar (Story 4.2).
          this.pendingCleanup = { variable: res.data.variable, profile };
        } else {
          // no_usable: bloque dedicado (UX-DR1), no el banner genérico de error.
          this.unusableInfo = { detail: profile.detail };
        }
      },
      error: () => {
        this.excelBusy = false;
        this.emitMessage('Ocurrió un error al cargar el Excel.', false);
      },
      complete: () => (input.value = ''),
    });
  }

  confirmCleanup(): void {
    if (!this.pendingCleanup) {
      return;
    }
    this.cleanupBusy = true;
    this.notebook.confirmExcelCleanup().subscribe({
      next: (res) => {
        this.cleanupBusy = false;
        this.pendingCleanup = null;
        this.emitMessage(res.message, res.success);
        if (res.success && res.data) {
          this.loaded.emit(res.data);
        }
      },
      error: () => {
        this.cleanupBusy = false;
        this.emitMessage('Ocurrió un error al confirmar la limpieza.', false);
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
  }

  private emitMessage(text: string, ok: boolean): void {
    this.message.emit({ text, ok });
  }
}
