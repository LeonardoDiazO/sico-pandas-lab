import { Component, EventEmitter, OnInit, Output } from '@angular/core';
import { retry, timer } from 'rxjs';

import { LoadResult, TableInfo } from '../../models/api.models';
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
    this.notebook.uploadExcel(file, 'df').subscribe({
      next: (res) => {
        this.excelBusy = false;
        this.emitMessage(res.message, res.success);
        if (res.success && res.data) {
          this.loaded.emit(res.data);
        }
      },
      error: () => {
        this.excelBusy = false;
        this.emitMessage('Ocurrió un error al cargar el Excel.', false);
      },
      complete: () => (input.value = ''),
    });
  }

  private emitMessage(text: string, ok: boolean): void {
    this.message.emit({ text, ok });
  }
}
