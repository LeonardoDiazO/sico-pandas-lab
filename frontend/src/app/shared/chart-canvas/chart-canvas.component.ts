import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import { Chart, ChartData, ChartOptions, registerables, TooltipItem } from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

import { looksLikeMoney, parseMoneyValue } from '../money-format';

// Chart.js 4's tree-shakeable registration requires every controller/
// element/scale/plugin it uses to be registered before a chart is built -
// registerables (everything the library ships) is simplest here since this
// component isn't performance-sensitive enough to hand-pick a subset, and
// Story 10.1's job is just getting an interactive chart on screen (fine
// tuning is 10.2-10.5).
Chart.register(...registerables, annotationPlugin);

// Story 10.5: reads a color straight off the app's shared design tokens
// (frontend/src/styles.scss's :root custom properties) at render time,
// instead of a hardcoded hex - if a token's value changes there, this
// chart picks it up with no code change here, per this story's own AC.
// Falls back to the token's current value only if getComputedStyle can't
// resolve it (e.g. a test environment with no stylesheet loaded). Review
// finding: these fallback hex literals duplicate styles.scss's :root
// values as of this writing and nothing keeps them in sync automatically -
// if a token's value changes there, update the matching fallback here too.
function designToken(name: string, fallback: string): string {
  if (typeof document === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

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
 * Story 10.4 adds the 80% crossing reference line (chartjs-plugin-
 * annotation), migrating the SVG's own `axhline(80)`. Story 10.5 reads
 * every chart-drawn color here (bars, cumulative line, 80% reference,
 * legend text, tooltip, axis ticks/grid) from the app's shared design
 * tokens (styles.scss), never a hardcoded hex.
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

  // Review finding (Story 10.5): getComputedStyle was being called on every
  // render()/update(), i.e. on every data change, even though this app has
  // no runtime theme switching (one :root block, no [data-theme] toggle) -
  // these values are effectively fixed per page load, so they're resolved
  // once per component instance and reused, instead of re-reading the
  // stylesheet on every regeneration.
  private colors?: {
    brand: string;
    secondary: string;
    referenceLine: string;
    text: string;
    grid: string;
    tooltipBg: string;
    tooltipText: string;
  };

  private resolveColors() {
    if (!this.colors) {
      this.colors = {
        brand: designToken('--brand', '#4a4fd6'),
        // Review finding (Story 10.5): --warn carries a "pay attention"/
        // caution connotation elsewhere in this app (banners, badges in
        // convatec-maestros, cell-result, etc.) - reusing it for a routine
        // cumulative-% line would misrepresent it as a warning. --brand-dark
        // reads as "secondary data series", not an alert.
        secondary: designToken('--brand-dark', '#363bab'),
        referenceLine: designToken('--ink-muted', '#5b6178'),
        text: designToken('--ink-muted', '#5b6178'),
        grid: designToken('--border', '#e2e4f1'),
        tooltipBg: designToken('--ink', '#1c2140'),
        tooltipText: designToken('--surface', '#ffffff'),
      };
    }
    return this.colors;
  }

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
    return `Gráfica de ${this.valueKey} por ${this.categoryKey}: ${this.records.length} categorías, con línea de % acumulado y referencia del 80%`;
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

    const colors = this.resolveColors();

    const data: ChartData<'bar' | 'line'> = {
      labels,
      datasets: [
        {
          type: 'bar',
          label: this.valueKey,
          data: values,
          yAxisID: 'y',
          backgroundColor: colors.brand,
        },
        {
          type: 'line',
          label: '% acumulado',
          data: cumulative,
          yAxisID: 'y1',
          tension: 0.2,
          pointRadius: 3,
          borderColor: colors.secondary,
          backgroundColor: colors.secondary,
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
        // Review finding (Story 10.5): legend text was left at Chart.js's
        // default gray instead of a token, undercutting the "every color"
        // claim above.
        legend: {
          labels: {
            color: colors.text,
          },
        },
        tooltip: {
          // Review finding (Story 10.5): same reasoning - the tooltip box
          // was left at Chart.js's default dark-gray/white instead of the
          // app's own ink/surface tokens.
          backgroundColor: colors.tooltipBg,
          titleColor: colors.tooltipText,
          bodyColor: colors.tooltipText,
          callbacks: {
            label: (context) => this.formatTooltipLabel(context),
          },
        },
        // Story 10.4: horizontal reference line at the 80% crossing on the
        // cumulative-% axis (y1) - migrates the SVG's own
        // `_ax2.axhline(80, ...)` (table_builder.py::_pareto_chart_lines),
        // not a new visual decision. --ink-muted (Story 10.5) also clears
        // the WCAG AA contrast bar the earlier #888888 placeholder missed -
        // white label text on --ink-muted is ≈6.1:1, over the 4.5:1 minimum.
        annotation: {
          annotations: {
            line80: {
              type: 'line',
              yMin: 80,
              yMax: 80,
              yScaleID: 'y1',
              borderColor: colors.referenceLine,
              borderWidth: 1,
              borderDash: [6, 4],
              label: {
                content: '80%',
                display: true,
                position: 'end',
                backgroundColor: colors.referenceLine,
              },
            },
          },
        },
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          beginAtZero: true,
          ticks: { color: colors.text },
          grid: { color: colors.grid },
        },
        y1: {
          type: 'linear',
          position: 'right',
          beginAtZero: true,
          min: 0,
          // Review finding (Story 10.4): the Python original left headroom
          // above the 80 line (`_ax2.set_ylim(0, 105)`,
          // table_builder.py::_pareto_chart_lines) so its label wouldn't
          // crowd the axis top - matched here for the same reason, not a
          // new value chosen independently.
          max: 105,
          ticks: { color: colors.text },
          grid: {
            drawOnChartArea: false,
          },
        },
        x: {
          ticks: { color: colors.text },
          grid: { color: colors.grid },
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
