import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApiResponse,
  ConvatecComisionResult,
  ConvatecMasterTablesResult,
  ConvatecProcesarResult,
  ConvatecVentasResult,
} from '../../models/api.models';

export type VentasTipo = 'productos' | 'servicios' | 'envios-nacionales';

@Injectable({ providedIn: 'root' })
export class ConvatecService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  uploadMasterTables(file: File): Observable<ApiResponse<ConvatecMasterTablesResult>> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ApiResponse<ConvatecMasterTablesResult>>(
      `${this.base}/api/convatec/tablas-maestras`,
      form,
    );
  }

  uploadVentas(tipo: VentasTipo, file: File): Observable<ApiResponse<ConvatecVentasResult>> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ApiResponse<ConvatecVentasResult>>(
      `${this.base}/api/convatec/ventas/${tipo}`,
      form,
    );
  }

  procesarCiclo(mes: number): Observable<ApiResponse<ConvatecProcesarResult>> {
    return this.http.post<ApiResponse<ConvatecProcesarResult>>(`${this.base}/api/convatec/procesar`, {
      mes,
    });
  }

  calcularComisionIlustrativa(valorReferencia: number): Observable<ApiResponse<ConvatecComisionResult>> {
    return this.http.post<ApiResponse<ConvatecComisionResult>>(
      `${this.base}/api/convatec/comision-ilustrativa`,
      { valorReferencia },
    );
  }

  /** Must go through HttpClient (not a plain <a href>) so SessionInterceptor
   * attaches X-Session-Id -- the backend keys the processed result by session. */
  descargarResultado(): Observable<Blob> {
    return this.http.get(`${this.base}/api/convatec/descargar`, { responseType: 'blob' });
  }

  reiniciarSesion(): Observable<ApiResponse<unknown>> {
    return this.http.post<ApiResponse<unknown>>(`${this.base}/api/convatec/reiniciar`, {});
  }
}
