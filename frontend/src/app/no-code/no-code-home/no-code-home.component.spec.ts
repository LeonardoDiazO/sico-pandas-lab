import { of } from 'rxjs';

import { DatasetService } from '../../core/dataset.service';
import { ToastService } from '../../core/toast.service';
import { LoadResult } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';
import { NoCodeHomeComponent } from './no-code-home.component';

const EXCEL: LoadResult = {
  variable: 'df',
  rows: 3,
  columns: ['a'],
  profile: { verdict: 'usable', headerRowIndex: 0, columns: [{ name: 'a', type: 'categorica' }], detail: '' },
};

const toast = () => new ToastService({ run: (f: () => void) => f() } as never);

// Step-by-step flow + following the shared session data (DatasetService).
describe('NoCodeHomeComponent', () => {
  let dataset: DatasetService;

  function make(preloaded?: (d: DatasetService) => void) {
    dataset = new DatasetService();
    preloaded?.(dataset);
    const notebook = {
      autoAnalysis: () => of({ success: true, status: 200, message: 'ok', data: { bloques: [{}], resumen: {} } }),
    } as unknown as NotebookService;
    return new NoCodeHomeComponent(notebook, toast(), dataset);
  }

  it('starts on step 1 and only opens step 2 once a file is loaded', () => {
    const c = make();
    expect(c.activeStep).toBe(1);
    expect(c.canGoTo(2)).toBeFalse();
    expect(c.nextBlockedReason).toContain('Sube un archivo');

    dataset.registerLoad(EXCEL, 'sin-codigo');
    expect(c.canGoTo(2)).toBeTrue();
    expect(c.canGoTo(3)).toBeFalse();
    c.goTo(2);
    expect(c.activeStep).toBe(2);
  });

  it('generating the dashboard jumps to step 3, and Anterior goes back', () => {
    const c = make();
    dataset.registerLoad(EXCEL, 'sin-codigo');
    c.goTo(2);
    c.onClassificationConfirmed([{ name: 'a', role: 'dimension' }]);
    expect(c.activeStep).toBe(3);
    c.goTo(c.prevStep!);
    expect(c.activeStep).toBe(2);
    expect(c.direction).toBe('back');
  });

  it('picks up an Excel loaded in another screen before this one opened, without a warning', () => {
    const c = make((d) => d.registerLoad(EXCEL, 'notebook'));
    expect(c.canGoTo(2)).toBeTrue();
    expect(c.dataChangedNote).toBeNull();
  });

  it('a new file from another screen resets the dashboard and says why', () => {
    const c = make();
    dataset.registerLoad(EXCEL, 'sin-codigo');
    c.onClassificationConfirmed([{ name: 'a', role: 'dimension' }]);
    expect(c.bloques.length).toBe(1);

    dataset.registerLoad({ ...EXCEL, rows: 9 }, 'notebook');
    expect(c.bloques.length).toBe(0);
    expect(c.activeStep).toBe(1);
    expect(c.dataChangedNote).toContain('el Notebook');
  });

  it('a session restart from another screen clears everything', () => {
    const c = make();
    dataset.registerLoad(EXCEL, 'sin-codigo');
    dataset.reset('notebook');
    expect(c.canGoTo(2)).toBeFalse();
    expect(c.dataChangedNote).toContain('reinició');
  });

  it('loading a sico table (its own df_<tabla>) does not touch the Excel analysis', () => {
    const c = make();
    dataset.registerLoad(EXCEL, 'sin-codigo');
    c.onClassificationConfirmed([{ name: 'a', role: 'dimension' }]);
    dataset.registerLoad({ variable: 'df_item', rows: 5, columns: ['x'] }, 'notebook');
    expect(c.bloques.length).toBe(1);
    expect(c.dataChangedNote).toBeNull();
  });
});
