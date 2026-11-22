import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

import { DataQuality, ExcelProfileColumn, LoadResult } from '../models/api.models';

export type DatasetOrigin = 'notebook' | 'sin-codigo' | 'guiado';

export const ORIGIN_LABELS: Record<DatasetOrigin, string> = {
  notebook: 'el Notebook',
  'sin-codigo': 'Sin código',
  guiado: 'el Módulo guiado',
};

/** The uploaded Excel currently bound in the backend session. */
export interface ExcelDataset {
  variable: string;
  rows: number;
  columns: ExcelProfileColumn[];
  quality: DataQuality | null;
  sheetsUsed: string[];
  origin: DatasetOrigin;
}

export interface SessionVariable {
  name: string;
  columns: string[];
}

export interface DatasetState {
  // Bumped on every load and on every session restart: a screen compares it
  // with the version it last applied to know its view is stale.
  version: number;
  excel: ExcelDataset | null;
  variables: SessionVariable[];
  // Why the last change happened - a load from some screen, or a restart.
  lastChange: { kind: 'load' | 'reset'; origin: DatasetOrigin | null };
}

/**
 * Single source of truth for "what data is loaded in this session", shared
 * by Notebook, Sin código and Módulo guiado. The screens stay alive while you
 * switch tabs (KeepAliveRouteReuseStrategy), so without this a file uploaded
 * in one tab would leave the others showing a dashboard or lesson built on
 * the previous data.
 */
@Injectable({ providedIn: 'root' })
export class DatasetService {
  readonly state$ = new BehaviorSubject<DatasetState>({
    version: 0,
    excel: null,
    variables: [],
    lastChange: { kind: 'reset', origin: null },
  });

  get state(): DatasetState {
    return this.state$.value;
  }

  /** Called by every data-source panel when something gets bound. */
  registerLoad(result: LoadResult, origin: DatasetOrigin): void {
    const current = this.state;
    const variables = current.variables.filter((v) => v.name !== result.variable);
    variables.push({ name: result.variable, columns: result.columns ?? [] });
    const profile = result.profile;
    const excel: ExcelDataset | null = profile
      ? {
          variable: result.variable,
          rows: result.rows,
          columns: profile.columns,
          quality: profile.quality ?? null,
          sheetsUsed: result.sheetsUsed ?? [],
          origin,
        }
      : // A sico table load binds its own df_<tabla>; it never replaces the
        // Excel, unless it was loaded under the same variable name.
        current.excel?.variable === result.variable
        ? null
        : current.excel;
    this.state$.next({ version: current.version + 1, excel, variables, lastChange: { kind: 'load', origin } });
  }

  /** The backend session was restarted: every bound variable is gone. */
  reset(origin: DatasetOrigin): void {
    this.state$.next({
      version: this.state.version + 1,
      excel: null,
      variables: [],
      lastChange: { kind: 'reset', origin },
    });
  }
}
