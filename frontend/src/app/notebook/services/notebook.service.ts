import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApiResponse,
  AutoAnalysisResult,
  CellResult,
  ChartResult,
  ClassifyColumnsResult,
  ColumnClassification,
  ColumnFilter,
  LoadResult,
  ParetoNarrativeResponse,
  ParetoStats,
  TablesPayload,
  TableResult,
} from '../../models/api.models';

@Injectable({ providedIn: 'root' })
export class NotebookService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  execute(code: string): Observable<ApiResponse<CellResult>> {
    return this.http.post<ApiResponse<CellResult>>(`${this.base}/api/notebook/execute`, { code });
  }

  restart(): Observable<ApiResponse<unknown>> {
    return this.http.post<ApiResponse<unknown>>(`${this.base}/api/notebook/restart`, {});
  }

  uploadExcel(file: File, variable: string): Observable<ApiResponse<LoadResult>> {
    const form = new FormData();
    form.append('file', file);
    form.append('variable', variable);
    return this.http.post<ApiResponse<LoadResult>>(`${this.base}/api/notebook/upload-excel`, form);
  }

  confirmExcelCleanup(excludeColumns: string[] = []): Observable<ApiResponse<LoadResult>> {
    return this.http.post<ApiResponse<LoadResult>>(`${this.base}/api/notebook/confirm-excel-cleanup`, {
      excludeColumns,
    });
  }

  cancelExcelCleanup(): Observable<ApiResponse<unknown>> {
    return this.http.post<ApiResponse<unknown>>(`${this.base}/api/notebook/cancel-excel-cleanup`, {});
  }

  generateChart(
    variable: string,
    columns: string[],
    valueColumn: string | null,
    chartType: string,
    force = false,
  ): Observable<ApiResponse<ChartResult>> {
    return this.http.post<ApiResponse<ChartResult>>(`${this.base}/api/notebook/generate-chart`, {
      variable,
      columns,
      valueColumn,
      chartType,
      force,
    });
  }

  sortTable(
    variable: string,
    valueColumn: string,
    ascending: boolean,
    filters: ColumnFilter[] = [],
  ): Observable<ApiResponse<TableResult>> {
    return this.http.post<ApiResponse<TableResult>>(`${this.base}/api/notebook/sort-table`, {
      variable,
      valueColumn,
      ascending,
      filters,
    });
  }

  summaryTable(
    variable: string,
    columns: string[],
    valueColumn: string,
    detail = false,
    filters: ColumnFilter[] = [],
  ): Observable<ApiResponse<TableResult>> {
    return this.http.post<ApiResponse<TableResult>>(`${this.base}/api/notebook/summary-table`, {
      variable,
      columns,
      valueColumn,
      detail,
      filters,
    });
  }

  // Story 8.4: distinct values of a column, for the "Filtrar por columna"
  // checkbox list (Excel-style: "choose which values to include").
  columnValues(variable: string, column: string): Observable<ApiResponse<TableResult>> {
    return this.http.post<ApiResponse<TableResult>>(`${this.base}/api/notebook/column-values`, {
      variable,
      column,
    });
  }

  // User feedback (replaces the removed deterministic/hardcoded comparison
  // text): sends the crossing stats AND the full row/group record lists
  // (user's explicit "Todo (los 88 grupos y las 171 filas completos)" after
  // asking why only a top-1 summary was sent) to the real assistant, once
  // both "Ordenar tabla" and "Resumen y porcentaje por columna" exist - see
  // pareto_narrative.py's security notes.
  paretoNarrative(
    valueColumnRow: string,
    rowStats: ParetoStats,
    rowRecords: Record<string, unknown>[],
    groupColumnsLabel: string,
    valueColumnGroup: string,
    groupStats: ParetoStats,
    groupRecords: Record<string, unknown>[],
  ): Observable<ApiResponse<ParetoNarrativeResponse>> {
    return this.http.post<ApiResponse<ParetoNarrativeResponse>>(`${this.base}/api/notebook/pareto-narrative`, {
      valueColumnRow,
      rowStats,
      rowRecords,
      groupColumnsLabel,
      valueColumnGroup,
      groupStats,
      groupRecords,
    });
  }

  // Capa semántica: suggests a role for every column of whatever Excel this
  // session already bound - no payload needed, the backend already knows
  // which DataFrame/profile belongs to this session (WorkerManager.
  // get_known_profile, same lookup the guided module uses).
  classifyColumns(): Observable<ApiResponse<ClassifyColumnsResult>> {
    return this.http.post<ApiResponse<ClassifyColumnsResult>>(`${this.base}/api/notebook/classify-columns`, {});
  }

  // Catálogo automático: runs a Pareto per dimension x metrica combination
  // the CONFIRMED (possibly user-corrected) classification enables - pure
  // pandas, no AI in this call.
  autoAnalysis(classifications: ColumnClassification[]): Observable<ApiResponse<AutoAnalysisResult>> {
    return this.http.post<ApiResponse<AutoAnalysisResult>>(`${this.base}/api/notebook/auto-analysis`, {
      classifications,
    });
  }

  listTables(): Observable<ApiResponse<TablesPayload>> {
    return this.http.get<ApiResponse<TablesPayload>>(`${this.base}/api/data/tables`);
  }

  loadTable(table: string, variable: string): Observable<ApiResponse<LoadResult>> {
    return this.http.post<ApiResponse<LoadResult>>(`${this.base}/api/data/load-table`, { table, variable });
  }
}
