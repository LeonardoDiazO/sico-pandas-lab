import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApiResponse,
  CellResult,
  ChartInterpretation,
  ChartResult,
  ExcelProfileColumn,
  LoadResult,
  TablesPayload,
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

  confirmExcelCleanup(): Observable<ApiResponse<LoadResult>> {
    return this.http.post<ApiResponse<LoadResult>>(`${this.base}/api/notebook/confirm-excel-cleanup`, {});
  }

  cancelExcelCleanup(): Observable<ApiResponse<unknown>> {
    return this.http.post<ApiResponse<unknown>>(`${this.base}/api/notebook/cancel-excel-cleanup`, {});
  }

  generateChart(
    variable: string,
    column: string | null,
    valueColumn: string | null,
    chartType: string,
    force = false,
  ): Observable<ApiResponse<ChartResult>> {
    return this.http.post<ApiResponse<ChartResult>>(`${this.base}/api/notebook/generate-chart`, {
      variable,
      column,
      valueColumn,
      chartType,
      force,
    });
  }

  interpretChartRequest(
    question: string,
    columns: ExcelProfileColumn[],
  ): Observable<ApiResponse<ChartInterpretation>> {
    return this.http.post<ApiResponse<ChartInterpretation>>(
      `${this.base}/api/notebook/interpret-chart-request`,
      { question, columns },
    );
  }

  listTables(): Observable<ApiResponse<TablesPayload>> {
    return this.http.get<ApiResponse<TablesPayload>>(`${this.base}/api/data/tables`);
  }

  loadTable(table: string, variable: string): Observable<ApiResponse<LoadResult>> {
    return this.http.post<ApiResponse<LoadResult>>(`${this.base}/api/data/load-table`, { table, variable });
  }
}
