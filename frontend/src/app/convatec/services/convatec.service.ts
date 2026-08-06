import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApiResponse,
  ConvatecComisionExternaResult,
  ConvatecComisionResult,
  ConvatecMaestrosResumen,
  ConvatecMasterTablesResult,
  ConvatecPreviewResult,
  ConvatecProcesarResult,
  ConvatecReconocimientoResult,
  ConvatecValidacionCifras,
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

  /** Maestros are global/persisted -- lets the UI show "ya cargado" on
   * page load without requiring a re-upload every session. */
  estadoMasterTables(): Observable<ApiResponse<ConvatecMasterTablesResult | null>> {
    return this.http.get<ApiResponse<ConvatecMasterTablesResult | null>>(
      `${this.base}/api/convatec/tablas-maestras`,
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

  previewResultado(limit = 50): Observable<ApiResponse<ConvatecPreviewResult>> {
    return this.http.get<ApiResponse<ConvatecPreviewResult>>(
      `${this.base}/api/convatec/resultado-preview?limit=${limit}`,
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

  maestrosResumen(): Observable<ApiResponse<ConvatecMaestrosResumen>> {
    return this.http.get<ApiResponse<ConvatecMaestrosResumen>>(`${this.base}/api/convatec/maestros-resumen`);
  }

  /** Explicit user decision (2026-08-06): stateless, never touches
   * Convatec's own data -- "COMISION POR VENTAS.xls" is confirmed to be
   * from a different client/system. */
  comisionExternaReferencia(file: File): Observable<ApiResponse<ConvatecComisionExternaResult>> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ApiResponse<ConvatecComisionExternaResult>>(
      `${this.base}/api/convatec/comision-externa-referencia`,
      form,
    );
  }

  /** Not an assignment input (step 10 of the original process, "SAP vs
   * Hyperion") -- only used for the total-vs-total check in validarCifras(). */
  uploadReconocimientoIngreso(file: File): Observable<ApiResponse<ConvatecReconocimientoResult>> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ApiResponse<ConvatecReconocimientoResult>>(
      `${this.base}/api/convatec/reconocimiento-ingreso`,
      form,
    );
  }

  validarCifras(): Observable<ApiResponse<ConvatecValidacionCifras>> {
    return this.http.get<ApiResponse<ConvatecValidacionCifras>>(`${this.base}/api/convatec/validacion-cifras`);
  }
}
