import { Component, Input, OnChanges } from '@angular/core';

import { AnalysisBlock, AnalysisSummary } from '../../models/api.models';
import { BLOCK_VIEWS, BlockView } from '../analysis-block/analysis-block.component';
import { buildParetoRows, formatValue } from '../pareto-data';

interface MetricGroup {
  metrica: string;
  bloques: AnalysisBlock[];
  total: number | null;
}

const VIEW_STORAGE_KEY = 'sico.dashboard.view';
const ALL = '__todas__';

function readStoredView(): BlockView {
  try {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY);
    if (BLOCK_VIEWS.some((v) => v.value === stored)) {
      return stored as BlockView;
    }
  } catch {
    // Storage blocked (private window, policy) - default below.
  }
  return 'pareto';
}

/**
 * The catálogo automático's output as an explorable dashboard: a summary of
 * what was analyzed (and what was left out, and why), one tab per métrica
 * so a wide file doesn't become an endless scroll, and a dashboard-wide
 * "ver como" control that switches every card's view at once. Each card
 * (app-analysis-block) stays independently explorable. Groups keep the
 * backend's own order (money-looking metrics first, analysis_catalog.py's
 * _prioritized_metrics) - never re-sorted here.
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

  readonly views = BLOCK_VIEWS;
  readonly ALL = ALL;
  readonly formatValue = formatValue;

  groups: MetricGroup[] = [];
  activeMetric: string = ALL;
  globalView: BlockView = readStoredView();

  ngOnChanges(): void {
    const byMetric = new Map<string, AnalysisBlock[]>();
    for (const bloque of this.bloques) {
      const list = byMetric.get(bloque.metrica);
      if (list) {
        list.push(bloque);
      } else {
        byMetric.set(bloque.metrica, [bloque]);
      }
    }
    this.groups = Array.from(byMetric.entries()).map(([metrica, bloques]) => ({
      metrica,
      bloques,
      total: this.metricTotal(bloques),
    }));
    // A single métrica needs no tabs; several start on the first (the
    // headline money metric) instead of every chart at once.
    if (!this.groups.some((g) => g.metrica === this.activeMetric)) {
      this.activeMetric = this.groups.length > 1 ? this.groups[0].metrica : ALL;
    }
  }

  // Every block of one métrica sums the same rows, just grouped differently -
  // any successful block's total is the métrica's grand total.
  private metricTotal(bloques: AnalysisBlock[]): number | null {
    for (const b of bloques) {
      if (b.resultado.error) {
        continue;
      }
      const rows = buildParetoRows(b.resultado.result_records, b.dimension, b.metrica);
      if (rows.length) {
        return rows.reduce((sum, r) => (Number.isFinite(r.value) ? sum + r.value : sum), 0);
      }
    }
    return null;
  }

  get visibleGroups(): MetricGroup[] {
    return this.activeMetric === ALL ? this.groups : this.groups.filter((g) => g.metrica === this.activeMetric);
  }

  get omitidas() {
    return this.resumen?.omitidas ?? [];
  }

  get demasiadas() {
    return this.omitidas.filter((o) => o.valores >= 2);
  }

  get unValor() {
    return this.omitidas.filter((o) => o.valores < 2);
  }

  setMetric(metrica: string): void {
    this.activeMetric = metrica;
  }

  onTabKeydown(event: KeyboardEvent, index: number): void {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!step) {
      return;
    }
    event.preventDefault();
    const ids = [ALL, ...this.groups.map((g) => g.metrica)];
    const next = (index + step + ids.length) % ids.length;
    this.activeMetric = ids[next];
    const list = (event.currentTarget as HTMLElement).parentElement;
    queueMicrotask(() => (list?.children[next] as HTMLElement | undefined)?.focus());
  }

  setGlobalView(view: BlockView): void {
    this.globalView = view;
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view);
    } catch {
      // Preference just won't persist.
    }
  }
}
