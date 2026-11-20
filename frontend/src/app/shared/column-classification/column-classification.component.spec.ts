import { of } from 'rxjs';

import { NotebookService } from '../../notebook/services/notebook.service';
import { ColumnClassificationComponent, suggestAggregation } from './column-classification.component';

describe('ColumnClassificationComponent aggregation', () => {
  it('suggests averaging rates and prices, summing everything else', () => {
    expect(suggestAggregation('Precio unitario')).toBe('mean');
    expect(suggestAggregation('% descuento')).toBe('mean');
    expect(suggestAggregation('Tasa de cambio')).toBe('mean');
    expect(suggestAggregation('Valor neto')).toBe('sum');
  });

  it('gives every suggested métrica an aggregation and sends it on confirm', () => {
    const notebook = {
      classifyColumns: () =>
        of({
          success: true,
          status: 200,
          message: 'ok',
          data: {
            usedAssistant: false,
            classifications: [
              { name: 'Cliente', role: 'dimension' },
              { name: 'Precio', role: 'metrica' },
              { name: 'Neto', role: 'metrica' },
            ],
          },
        }),
    } as unknown as NotebookService;
    const component = new ColumnClassificationComponent(notebook);
    component.profile = { variable: 'df', columns: [] };
    component.fetchSuggestion();
    let sent: unknown = null;
    component.confirmed.subscribe((c) => (sent = c));

    component.setAgg('Neto', 'count');
    component.confirm();

    expect(sent).toEqual([
      { name: 'Cliente', role: 'dimension' },
      { name: 'Precio', role: 'metrica', agg: 'mean' },
      { name: 'Neto', role: 'metrica', agg: 'count' },
    ]);
  });
});
