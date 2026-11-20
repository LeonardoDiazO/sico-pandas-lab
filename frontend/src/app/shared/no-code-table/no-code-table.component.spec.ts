import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { NotebookService } from '../../notebook/services/notebook.service';
import { NoCodeTableComponent } from './no-code-table.component';

// Decisión #2: nothing reaches the external assistant until the user confirms
// a dialog that states what is sent - and what is sent is exactly that.
describe('NoCodeTableComponent narrative consent', () => {
  let http: HttpTestingController;
  let component: NoCodeTableComponent;

  const stats = {
    valueColumnRow: 'Neto',
    rowStats: { total: 2, cruce_80: 1, pct_base: 50 },
    rowRecords: [
      { Cliente: 'Ana', Neto: 100 },
      { Cliente: 'Luis', Neto: 50 },
    ],
    groupColumnsLabel: 'Cliente',
    valueColumnGroup: 'Neto',
    groupStats: { total: 2, cruce_80: 1, pct_base: 50 },
    groupRecords: [{ Cliente: 'Ana', Neto: 100 }],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    component = new NoCodeTableComponent(TestBed.inject(NotebookService));
    spyOn(component as unknown as { buildNarrativeStats: () => unknown }, 'buildNarrativeStats').and.returnValue(stats);
  });

  afterEach(() => http.verify());

  it('asking shows what will be sent and sends nothing yet', () => {
    component.askNarrativeConsent();
    expect(component.consentPreview).toEqual({ rows: 2, groups: 1, columns: ['Cliente', 'Neto'] });
    http.expectNone((r) => r.url.endsWith('/pareto-narrative'));
  });

  it('cancel sends nothing', () => {
    component.askNarrativeConsent();
    component.cancelNarrativeConsent();
    component.generateNarrative();
    http.expectNone((r) => r.url.endsWith('/pareto-narrative'));
    expect(component.consentPreview).toBeNull();
  });

  it('confirming sends exactly the approved rows, with consent', () => {
    component.askNarrativeConsent();
    component.generateNarrative();
    const req = http.expectOne((r) => r.url.endsWith('/pareto-narrative'));
    expect(req.request.body.consent).toBeTrue();
    expect(req.request.body.rowRecords).toEqual(stats.rowRecords);
    expect(req.request.body.groupRecords).toEqual(stats.groupRecords);
    req.flush({ success: true, status: 200, message: 'ok', data: { narrative: 'texto' } });
    expect(component.narrativeText).toBe('texto');
  });
});
