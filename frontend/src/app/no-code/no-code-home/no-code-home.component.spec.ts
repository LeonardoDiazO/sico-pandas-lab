import { of } from 'rxjs';

import { ToastService } from '../../core/toast.service';
import { NotebookService } from '../../notebook/services/notebook.service';
import { NoCodeHomeComponent } from './no-code-home.component';

// Step-by-step flow: one step on screen, moved with Anterior/Siguiente.
describe('NoCodeHomeComponent wizard', () => {
  function make(autoAnalysis = () => of({ success: true, status: 200, message: 'ok', data: { bloques: [{}], resumen: {} } })) {
    const notebook = { autoAnalysis } as unknown as NotebookService;
    return new NoCodeHomeComponent(notebook, new ToastService({ run: (f: () => void) => f() } as never));
  }

  it('starts on step 1 and only opens step 2 once a file is loaded', () => {
    const c = make();
    expect(c.activeStep).toBe(1);
    expect(c.canGoTo(2)).toBeFalse();
    expect(c.nextBlockedReason).toContain('Sube un archivo');
    c.goTo(2);
    expect(c.activeStep).toBe(1);

    c.onLoaded({ variable: 'df', rows: 3, columns: ['a'], profile: { verdict: 'usable', headerRowIndex: 0, columns: [], detail: '' } });
    expect(c.canGoTo(2)).toBeTrue();
    expect(c.canGoTo(3)).toBeFalse();
    c.goTo(2);
    expect(c.activeStep).toBe(2);
    expect(c.direction).toBe('forward');
  });

  it('generating the dashboard jumps to step 3, and Anterior goes back', () => {
    const c = make();
    c.onLoaded({ variable: 'df', rows: 3, columns: ['a'], profile: { verdict: 'usable', headerRowIndex: 0, columns: [], detail: '' } });
    c.goTo(2);
    c.onClassificationConfirmed([{ name: 'a', role: 'dimension' }]);
    expect(c.activeStep).toBe(3);
    expect(c.isDone(2)).toBeTrue();
    c.goTo(c.prevStep!);
    expect(c.activeStep).toBe(2);
    expect(c.direction).toBe('back');
  });
});
