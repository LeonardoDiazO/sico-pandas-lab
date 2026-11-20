import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { LoadResult } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';
import { DataSourcePanelComponent } from './data-source-panel.component';

// Decisión #4: a multi-sheet workbook stops at a sheet picker; nothing is
// "loaded" until the chosen sheets come back bound.
describe('DataSourcePanelComponent sheet selection', () => {
  let http: HttpTestingController;
  let component: DataSourcePanelComponent;
  let loaded: LoadResult[];

  const ok = (data: Partial<LoadResult>) => ({ success: true, status: 200, message: 'ok', data: data as LoadResult });

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    component = new DataSourcePanelComponent(TestBed.inject(NotebookService));
    loaded = [];
    component.loaded.subscribe((r) => loaded.push(r));
  });

  afterEach(() => http.verify());

  function upload(): void {
    (component as unknown as { uploadFile(f: File): void }).uploadFile(new File(['x'], 'libro.xlsx'));
  }

  it('a multi-sheet reply shows the picker, pre-selects only usable sheets and emits nothing', () => {
    upload();
    http.expectOne((r) => r.url.endsWith('/upload-excel')).flush(
      ok({
        variable: 'df',
        rows: 0,
        columns: [],
        needsSheetSelection: true,
        sheets: [
          { name: 'Portada', rows: 0, columns: 0, headerRowIndex: null, verdict: 'no_usable', detail: '', usable: false },
          { name: 'Enero', rows: 10, columns: 3, headerRowIndex: 0, verdict: 'usable', detail: '', usable: true },
          { name: 'Febrero', rows: 8, columns: 3, headerRowIndex: 0, verdict: 'usable', detail: '', usable: true },
        ],
      }),
    );
    expect(loaded.length).toBe(0);
    expect(component.pendingSheets?.length).toBe(3);
    expect([...component.chosenSheets]).toEqual(['Enero', 'Febrero']);
  });

  it('confirming posts the chosen sheets in workbook order and emits the bound result', () => {
    upload();
    http.expectOne((r) => r.url.endsWith('/upload-excel')).flush(
      ok({
        variable: 'df',
        needsSheetSelection: true,
        sheets: [
          { name: 'Enero', rows: 10, columns: 3, headerRowIndex: 0, verdict: 'usable', detail: '', usable: true },
          { name: 'Febrero', rows: 8, columns: 3, headerRowIndex: 0, verdict: 'usable', detail: '', usable: true },
        ],
      }),
    );
    component.toggleSheet('Enero');
    component.toggleSheet('Enero'); // re-checked: order must still follow the workbook
    component.confirmSheets();
    const req = http.expectOne((r) => r.url.endsWith('/select-sheets'));
    expect(req.request.body).toEqual({ sheets: ['Enero', 'Febrero'] });
    req.flush(
      ok({
        variable: 'df',
        rows: 18,
        columns: ['Hoja', 'cliente', 'neto'],
        bound: true,
        sheetsUsed: ['Enero', 'Febrero'],
        profile: { verdict: 'usable', headerRowIndex: null, columns: [], detail: '' },
      }),
    );
    expect(loaded.length).toBe(1);
    expect(loaded[0].sheetsUsed).toEqual(['Enero', 'Febrero']);
    expect(component.pendingSheets).toBeNull();
  });

  it('a stacked result that needs cleanup opens the cleanup step instead of loading', () => {
    upload();
    http.expectOne((r) => r.url.endsWith('/upload-excel')).flush(
      ok({
        variable: 'df',
        needsSheetSelection: true,
        sheets: [
          { name: 'A', rows: 5, columns: 2, headerRowIndex: 2, verdict: 'usable_con_limpieza', detail: '', usable: true },
          { name: 'B', rows: 5, columns: 2, headerRowIndex: 2, verdict: 'usable_con_limpieza', detail: '', usable: true },
        ],
      }),
    );
    component.confirmSheets();
    http.expectOne((r) => r.url.endsWith('/select-sheets')).flush(
      ok({
        variable: 'df',
        rows: 10,
        columns: ['Hoja', 'x'],
        profile: { verdict: 'usable_con_limpieza', headerRowIndex: 2, columns: [], detail: 'limpiar' },
      }),
    );
    expect(loaded.length).toBe(0);
    expect(component.pendingCleanup).not.toBeNull();
  });
});
