import { Component, Input, OnChanges } from '@angular/core';

import { AnalysisBlock, AnalysisSummary } from '../../models/api.models';

interface MetricGroup {
  metrica: string;
  bloques: AnalysisBlock[];
}

/**
 * Renders the catálogo automático's output: an executive-summary strip
 * (rows analyzed, dimensions/metrics considered, blocks generated) followed
 * by one section per métrica, each with a card per dimension - "contexto
 * amplio antes del detalle" (user feedback) instead of a flat, unordered
 * pile of charts. Reuses app-cell-result (the same component that already
 * renders chart_svg/result_html everywhere else in the app) for each card's
 * table+chart - zero new rendering logic for the numbers themselves.
 */
@Component({
  selector: 'app-analysis-dashboard',
  standalone: false,
  templateUrl: './analysis-dashboard.component.html',
  styleUrl: './analysis-dashboard.component.scss',
})
export class AnalysisDashboardComponent implements OnChanges {
  @Input() bloques: AnalysisBlock[] = [];
  @Input() resumen: AnalysisSummary | null = null;

  groups: MetricGroup[] = [];

  ngOnChanges(): void {
    // Groups while preserving the backend's own order (money-looking
    // metrics first, see analysis_catalog.py's _prioritized_metrics) -
    // never re-sorts, just folds consecutive-by-metric blocks into
    // sections instead of one flat grid.
    const byMetric = new Map<string, AnalysisBlock[]>();
    for (const bloque of this.bloques) {
      const list = byMetric.get(bloque.metrica);
      if (list) {
        list.push(bloque);
      } else {
        byMetric.set(bloque.metrica, [bloque]);
      }
    }
    this.groups = Array.from(byMetric.entries()).map(([metrica, bloques]) => ({ metrica, bloques }));
  }
}
