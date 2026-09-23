import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import { Chart, ChartData, ChartOptions, registerables, TooltipItem } from 'chart.js';

import { looksLikeMoney, parseMoneyValue } from '../money-format';

// Chart.js 4's tree-shakeable registration requires every controller/
// element/scale/plugin it uses to be registered before a chart is built -
// registerables (everything the library ships) is simplest here since this
// component isn't performance-sensitive enough to hand-pick a subset, and
// Story 10.1's job is just getting an interactive chart on screen (fine
// tuning is 10.2-10.5).
Chart.register(...registerables);

// Story 10.3's own animation duration, named so the doc comment, the runtime
// config, and the test asserting it all point at one source of truth.
const ENTRY_ANIMATION_DURATION_MS = 700;

// Review finding (Story 10.3): a CSS `@media (prefers-reduced-motion)` rule
// (the pattern already used in no-code-home.component.scss and
// column-classification.component.scss) can't reach into a Chart.js canvas
// animation - it has to be a JS-side check, read fresh on every render() so
// a mid-session OS setting change is honored, not just at module load.
function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
}

/**
 * Interactive Pareto chart (bars = raw value, line = cumulative % on a
 * second axis) for the automatic dashboard (`analysis-dashboard.component`),
 * fed directly from `result_records` - the same rows `table_builder.py`'s
 * `build_summary_code` already returns, no backend change needed. Replaces
 * the static `chart_svg` matplotlib image ONLY inside that dashboard; every
 * other consumer of `cell-result.component` (free notebook, guided module)
 * keeps rendering `chart_svg` untouched (see `hideChart` there).
 *
 * Story 10.2 adds a combined tooltip (bar value + cumulative % together,
 * touch-tappable - Chart.js' default `events` already include touch).
 * Story 10.3 sets an explicit sub-1s entry/update animation duration.
 * Colors and the 80% line annotation stay vanilla Chart.js defaults for
 * now - those are Stories 10.4-10.5.
 */
@Component({
  selector: 'app-chart-canvas',
  standalone: false,
  templateUrl: './chart-canvas.component.html',
  styleUrl: './chart-canvas.component.scss',
})
export class ChartCanvasComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() records: Record<string, unknown>[] = [];
  @Input() categoryKey = '';
  @Input() valueKey = '';

  @ViewChild('canvasEl') private canvasEl?: ElementRef<HTMLCanvasElement>;

  private chart: Chart | null = null;
  private viewReady = false;

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.render();
  }

  ngOnChanges(_changes: SimpleChanges): void {
    // Guards ngOnChanges firing before ngAfterViewInit (Angular calls
    // ngOnChanges with the initial @Input values before the view - and its
    // ViewChild canvas - exists).
    if (this.viewReady) {
      this.render();
    }
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }

  // The previous chart_svg image gave screen readers a native per-bar
  // <title> tooltip (execution.py::_inject_svg_tooltips) - a bare <canvas>
  // has no text alternative at all, so this replaces it with one summary
  // label describing what the chart shows (not per-bar, but not silent
  // either).
  get chartAriaLabel(): string {
    return `Gráfica de ${this.valueKey} por ${this.categoryKey}: ${this.records.length} categorías, con línea de % acumulado`;
  }

  // Backend value columns that "look like money" (table_builder.py's
  // _looks_like_money/_money_format_expr) arrive pre-formatted as strings
  // like "$ 12.345" (a "$ " prefix, "." thousands separators, no decimals)
  // rather than raw numbers - detect the string shape here and parse it
  // back into a real number for the chart via the shared money-format
  // helper (kept there, not inlined, so it stays in sync with the
  // backend's formatting). A value that's already a number (a non-money
  // metric) is used as-is. NaN (not 0) for anything else/unparseable, so
  // Chart.js shows a gap instead of a misleading zero-height bar.
  private toNumber(raw: unknown): number {
    if (typeof raw === 'number') {
      return raw;
    }
    if (typeof raw === 'string') {
      return parseMoneyValue(raw);
    }
    return NaN;
  }

  // Review finding (Story 10.2): the bar dataset's raw number came from
  // parseMoneyValue() for money columns, so the "$ " prefix is gone by the
  // time it reaches here - re-checking looksLikeMoney(valueKey) (same
  // shared helper) puts it back, matching the table right next to this
  // chart instead of showing a bare number for a money metric. Non-money
  // metrics keep up to 2 decimals instead of always rounding to an integer
  // - "valor exacto" (this story's own AC) means not silently truncating a
  // ratio/average's precision the way a money amount is expected to be.
  private formatTooltipLabel(context: TooltipItem<'bar' | 'line'>): string {
    const value = context.parsed.y;
    if (value === null || !Number.isFinite(value)) {
      return `${context.dataset.label}: sin dato`;
    }
    if (context.dataset.type === 'line') {
      return `${context.dataset.label}: ${value.toFixed(1)}%`;
    }
    if (looksLikeMoney(this.valueKey)) {
      return `${context.dataset.label}: $ ${Math.round(value).toLocaleString('es-CO')}`;
    }
    return `${context.dataset.label}: ${value.toLocaleString('es-CO', { maximumFractionDigits: 2 })}`;
  }

  private render(): void {
    const canvas = this.canvasEl?.nativeElement;
    if (!canvas || !this.categoryKey || !this.valueKey) {
      return;
    }

    const labels = this.records.map((record) => String(record[this.categoryKey] ?? ''));
    const values = this.records.map((record) => this.toNumber(record[this.valueKey]));
    const cumulative = this.records.map((record) => this.toNumber(record['% acumulado']));

    const data: ChartData<'bar' | 'line'> = {
      labels,
      datasets: [
        {
          type: 'bar',
          label: this.valueKey,
          data: values,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: '% acumulado',
          data: cumulative,
          yAxisID: 'y1',
          tension: 0.2,
          pointRadius: 3,
        },
      ],
    };

    const options: ChartOptions<'bar' | 'line'> = {
      responsive: true,
      maintainAspectRatio: false,
      // Story 10.3: explicit duration under 1s (the AC's own wording) —
      // Chart.js's undocumented-here default (1000ms) sits right at that
      // boundary and could change with a library upgrade. Applies to both
      // the initial render AND every chart.update() below (Chart.js
      // animates value transitions on update() the same way it animates
      // the first draw) — regenerating with a different column replays
      // this same animation into the existing Chart instance, never a
      // second one, so nothing duplicates on screen. `easeOutQuart` is
      // Chart.js's own current default easing - pinned explicitly for the
      // same reason as duration (protect against a future library default
      // change), not a new stylistic choice. Duration collapses to 0 under
      // `prefers-reduced-motion: reduce`, matching the reduced-motion
      // convention already used elsewhere in this app (CSS there; JS here,
      // since a canvas animation is outside CSS's reach).
      animation: {
        duration: prefersReducedMotion() ? 0 : ENTRY_ANIMATION_DURATION_MS,
        easing: 'easeOutQuart',
      },
      // 'index' + intersect:false (Story 10.2): hovering (or tapping, on
      // touch - Chart.js' default `events` list already includes
      // touchstart/touchmove, no extra config needed for that part) a bar
      // shows BOTH datasets at that category in one tooltip, not just the
      // one the pointer happens to be over - the AC needs the value and
      // the % acumulado together, not as two separate hovers.
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (context) => this.formatTooltipLabel(context),
          },
        },
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          beginAtZero: true,
        },
        y1: {
          type: 'linear',
          position: 'right',
          beginAtZero: true,
          min: 0,
          max: 100,
          grid: {
            drawOnChartArea: false,
          },
        },
      },
    };

    if (this.chart) {
      this.chart.data = data;
      this.chart.options = options;
      this.chart.update();
      return;
    }

    this.chart = new Chart(canvas, {
      type: 'bar',
      data,
      options,
    });
  }
}
