import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  NgZone,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { ActiveElement, Chart, ChartConfiguration, ChartEvent, Plugin, registerables, TooltipItem } from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

import { looksLikeMoney } from '../money-format';
import { buildParetoRows, formatCompact, formatPct, formatValue, ParetoRow } from '../pareto-data';

Chart.register(...registerables, annotationPlugin);

/**
 * Views the automatic dashboard can switch between for the same Pareto
 * summary - all drawn from the same normalized ParetoRows:
 * - pareto: bars + cumulative-% line + 80% reference (the classic diagram
 *   users asked for "con sus ejes en porcentaje").
 * - ranking: horizontal bars, one axis, every category name readable in
 *   full and its share printed at the bar end - the easiest view for
 *   someone who has never read a Pareto chart.
 * - dona: share of the total (top 5 + "Otros"), for "how big is each slice".
 */
export type ChartView = 'pareto' | 'ranking' | 'dona';

// Reads a color off the app's shared design tokens (styles.scss :root) at
// render time instead of a hardcoded hex. The fallbacks duplicate the
// current token values - keep them in sync if styles.scss changes.
function designToken(name: string, fallback: string): string {
  if (typeof document === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

const ENTRY_ANIMATION_DURATION_MS = 700;

// Donut slices: validated categorical order (dataviz reference palette,
// slots 1-5 adjacent-pair CVD-safe) - "Otros" always takes the neutral.
// Every slice also carries its name + share in the legend and table view,
// so identity is never color-alone.
const SLICE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
const MAX_SLICES = 5;

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
}

function withAlpha(color: string, alpha: number): string {
  // Tokens are hex in styles.scss; rgb()/other forms (tests, overrides) are
  // returned untouched rather than mangled.
  const hex = color.trim();
  if (/^#[0-9a-f]{6}$/i.test(hex)) {
    const a = Math.round(alpha * 255)
      .toString(16)
      .padStart(2, '0');
    return `${hex}${a}`;
  }
  return color;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/**
 * Interactive canvas chart for the automatic dashboard, fed directly from
 * `result_records` (no backend change, no static image). Hover/tap shows a
 * combined tooltip; clicking a bar or slice selects that category
 * (`selectedIndexChange`) so the surrounding card can show its detail and
 * highlight it in the table view. Bars belonging to the 80% "vital few" are
 * drawn in the brand color and the rest muted, so the 80/20 split reads
 * without decoding the cumulative line first.
 *
 * Chart.js runs entirely outside Angular's zone: its ResizeObserver and rAF
 * loop otherwise re-enter change detection on every tick, which inside the
 * dashboard's CSS grid fed a real resize/CD loop that froze the browser.
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
  @Input() view: ChartView = 'pareto';
  // null = every category; otherwise only the top N (already sorted desc).
  @Input() topN: number | null = null;
  @Input() selectedIndex: number | null = null;
  @Input() height = 320;
  @Output() selectedIndexChange = new EventEmitter<number | null>();

  @ViewChild('canvasEl') private canvasEl?: ElementRef<HTMLCanvasElement>;

  private chart: Chart | null = null;
  private chartView: ChartView | null = null;
  private viewReady = false;
  private rows: ParetoRow[] = [];

  constructor(private ngZone: NgZone) {}

  private colors?: {
    brand: string;
    muted: string;
    secondary: string;
    referenceLine: string;
    text: string;
    grid: string;
    tooltipBg: string;
    tooltipText: string;
    surface: string;
    ink: string;
    other: string;
  };

  private resolveColors() {
    if (!this.colors) {
      this.colors = {
        brand: designToken('--brand', '#4a4fd6'),
        muted: designToken('--chart-muted', '#c3c6ec'),
        secondary: designToken('--brand-dark', '#363bab'),
        referenceLine: designToken('--ink-muted', '#5b6178'),
        text: designToken('--ink-muted', '#5b6178'),
        grid: designToken('--border', '#e2e4f1'),
        tooltipBg: designToken('--ink', '#1c2140'),
        tooltipText: designToken('--surface', '#ffffff'),
        surface: designToken('--surface', '#ffffff'),
        ink: designToken('--ink', '#1c2140'),
        other: designToken('--ink-faint', '#8a90a8'),
      };
    }
    return this.colors;
  }

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.render();
  }

  ngOnChanges(_changes: SimpleChanges): void {
    if (this.viewReady) {
      this.render();
    }
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
    this.chart = null;
  }

  get chartAriaLabel(): string {
    const viewLabel =
      this.view === 'ranking'
        ? 'Ranking de barras horizontales'
        : this.view === 'dona'
          ? 'Gráfica de participación'
          : 'Gráfica de Pareto';
    const vital = buildParetoRows(this.records, this.categoryKey, this.valueKey).filter((r) => r.vital).length;
    return `${viewLabel} de ${this.valueKey} por ${this.categoryKey}: ${this.records.length} categorías; ${vital} concentran el 80% del total. Los valores exactos están en la vista Tabla.`;
  }

  /** PNG data URL of the current chart (surface-filled, not transparent). */
  toPng(): string | null {
    return this.chart ? this.chart.toBase64Image('image/png', 1) : null;
  }

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
    this.ngZone.runOutsideAngular(() => this.renderChart());
  }

  private visibleRows(): ParetoRow[] {
    return this.topN ? this.rows.slice(0, this.topN) : this.rows;
  }

  private barColors(rows: ParetoRow[]): string[] {
    const c = this.resolveColors();
    return rows.map((row, i) => {
      const base = row.vital ? c.brand : c.muted;
      if (this.selectedIndex === null || this.selectedIndex === i) {
        return base;
      }
      return withAlpha(base, 0.35);
    });
  }

  private onChartClick(_event: ChartEvent, elements: ActiveElement[]): void {
    const hit = elements[0];
    let index: number | null = hit ? hit.index : null;
    // The donut's last slice can be the synthetic "Otros" - not a real row.
    if (index !== null && this.view === 'dona' && index >= MAX_SLICES && this.rows.length > MAX_SLICES) {
      index = null;
    }
    const next = index === this.selectedIndex ? null : index;
    this.ngZone.run(() => this.selectedIndexChange.emit(next));
  }

  // Fills the canvas with the surface color first so a downloaded PNG isn't
  // transparent (black in most image viewers).
  private surfacePlugin(): Plugin {
    return {
      id: 'surfaceFill',
      beforeDraw: (chart) => {
        const ctx = chart.ctx;
        ctx.save();
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = this.resolveColors().surface;
        ctx.fillRect(0, 0, chart.width, chart.height);
        ctx.restore();
      },
    };
  }

  // Ranking view: share printed at each bar's end (selective direct label -
  // one short number per bar, in text ink, never the series color).
  private barEndLabelsPlugin(): Plugin<'bar'> {
    return {
      id: 'barEndLabels',
      afterDatasetsDraw: (chart) => {
        if (this.chartView !== 'ranking') {
          return;
        }
        const meta = chart.getDatasetMeta(0);
        const rows = this.visibleRows();
        const c = this.resolveColors();
        const ctx = chart.ctx;
        ctx.save();
        ctx.font = '600 11px Inter, system-ui, sans-serif';
        ctx.fillStyle = c.ink;
        ctx.textBaseline = 'middle';
        meta.data.forEach((bar, i) => {
          const row = rows[i];
          if (!row || !Number.isFinite(row.value)) {
            return;
          }
          const { x, y } = bar.getProps(['x', 'y'], true) as { x: number; y: number };
          ctx.fillText(formatPct(row.pct), x + 6, y);
        });
        ctx.restore();
      },
    };
  }

  // Donut: grand total in the hole, so the part-to-whole has its whole.
  private centerTotalPlugin(): Plugin<'doughnut'> {
    return {
      id: 'centerTotal',
      afterDraw: (chart) => {
        if (this.chartView !== 'dona') {
          return;
        }
        const meta = chart.getDatasetMeta(0);
        const arc = meta.data[0] as unknown as { x: number; y: number; innerRadius: number } | undefined;
        if (!arc || arc.innerRadius < 40) {
          return;
        }
        const total = this.rows.reduce((sum, r) => (Number.isFinite(r.value) ? sum + r.value : sum), 0);
        const c = this.resolveColors();
        const ctx = chart.ctx;
        ctx.save();
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = c.text;
        ctx.font = '600 11px Inter, system-ui, sans-serif';
        ctx.fillText('Total', arc.x, arc.y - 11);
        ctx.fillStyle = c.ink;
        ctx.font = '700 15px Inter, system-ui, sans-serif';
        ctx.fillText(formatCompact(total, this.valueKey), arc.x, arc.y + 8);
        ctx.restore();
      },
    };
  }

  private baseTooltip() {
    const c = this.resolveColors();
    return {
      backgroundColor: c.tooltipBg,
      titleColor: c.tooltipText,
      bodyColor: c.tooltipText,
      padding: 10,
      cornerRadius: 8,
      boxPadding: 4,
      titleFont: { weight: 'bold' as const },
    };
  }

  private paretoConfig(): ChartConfiguration<'bar' | 'line'> {
    const c = this.resolveColors();
    const rows = this.visibleRows();
    return {
      type: 'bar',
      data: {
        labels: rows.map((r) => r.label),
        datasets: [
          {
            type: 'bar',
            label: this.valueKey,
            data: rows.map((r) => r.value),
            yAxisID: 'y',
            backgroundColor: this.barColors(rows),
            borderRadius: 4,
            borderSkipped: 'bottom',
            maxBarThickness: 56,
          },
          {
            type: 'line',
            label: '% acumulado',
            data: rows.map((r) => r.cum),
            yAxisID: 'y1',
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            borderColor: c.secondary,
            backgroundColor: c.secondary,
          },
        ],
      },
      options: {
        ...this.commonOptions(),
        interaction: { mode: 'index', intersect: false },
        plugins: {
          // Identity lives in the card's own legend line (vital / resto /
          // % acumulado) - a second Chart.js legend just repeated it.
          legend: { display: false },
          tooltip: {
            ...this.baseTooltip(),
            callbacks: {
              label: (context) => this.formatTooltipLabel(context),
              afterBody: (items) => {
                const row = rows[items[0]?.dataIndex ?? -1];
                return row ? [`${formatPct(row.pct)} del total${row.vital ? ' · parte del 80%' : ''}`] : [];
              },
            },
          },
          annotation: {
            annotations: {
              line80: {
                type: 'line',
                yMin: 80,
                yMax: 80,
                yScaleID: 'y1',
                borderColor: c.referenceLine,
                borderWidth: 1,
                borderDash: [6, 4],
                label: {
                  content: '80%',
                  display: true,
                  position: 'end',
                  backgroundColor: c.referenceLine,
                  font: { size: 10, weight: 'bold' },
                  padding: { x: 6, y: 3 },
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
            border: { display: false },
            ticks: { color: c.text, callback: (v) => formatCompact(Number(v), this.valueKey), maxTicksLimit: 6 },
            grid: { color: c.grid },
          },
          y1: {
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            min: 0,
            max: 105,
            border: { display: false },
            ticks: { color: c.text, stepSize: 20, callback: (v) => (Number(v) <= 100 ? `${v}%` : '') },
            grid: { drawOnChartArea: false },
          },
          x: {
            ticks: {
              color: c.text,
              autoSkip: true,
              maxRotation: 45,
              callback: (_v, i) => truncate(rows[i]?.label ?? '', 14),
            },
            grid: { display: false },
          },
        },
      },
    };
  }

  private rankingConfig(): ChartConfiguration<'bar'> {
    const c = this.resolveColors();
    const rows = this.visibleRows();
    return {
      type: 'bar',
      data: {
        labels: rows.map((r) => r.label),
        datasets: [
          {
            label: this.valueKey,
            data: rows.map((r) => r.value),
            backgroundColor: this.barColors(rows),
            borderRadius: 4,
            borderSkipped: 'start',
            maxBarThickness: 26,
            categoryPercentage: 0.85,
            barPercentage: 0.9,
          },
        ],
      },
      options: {
        ...this.commonOptions(),
        indexAxis: 'y',
        layout: { padding: { right: 44 } },
        interaction: { mode: 'nearest', axis: 'y', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...this.baseTooltip(),
            callbacks: {
              label: (context) => `${this.valueKey}: ${formatValue(Number(context.parsed.x), this.valueKey)}`,
              afterLabel: (context) => {
                const row = rows[context.dataIndex];
                return row ? `${formatPct(row.pct)} del total · acumulado ${formatPct(row.cum)}` : '';
              },
            },
          },
          annotation: { annotations: {} },
        },
        scales: {
          x: {
            beginAtZero: true,
            border: { display: false },
            ticks: { color: c.text, callback: (v) => formatCompact(Number(v), this.valueKey), maxTicksLimit: 5 },
            grid: { color: c.grid },
          },
          y: {
            border: { display: false },
            ticks: {
              color: c.ink,
              autoSkip: false,
              font: { size: 12 },
              callback: (_v, i) => truncate(rows[i]?.label ?? '', 24),
            },
            grid: { display: false },
          },
        },
      },
    };
  }

  private donutConfig(): ChartConfiguration<'doughnut'> {
    const c = this.resolveColors();
    const named = this.rows.slice(0, MAX_SLICES);
    const rest = this.rows.slice(MAX_SLICES);
    const labels = named.map((r) => r.label);
    const values = named.map((r) => (Number.isFinite(r.value) ? Math.max(r.value, 0) : 0));
    const pcts = named.map((r) => r.pct);
    const colors = named.map((_r, i) => SLICE_COLORS[i]);
    if (rest.length) {
      labels.push(`Otros (${rest.length})`);
      values.push(rest.reduce((s, r) => (Number.isFinite(r.value) ? s + Math.max(r.value, 0) : s), 0));
      pcts.push(rest.reduce((s, r) => s + r.pct, 0));
      colors.push(c.other);
    }
    const faded = colors.map((col, i) =>
      this.selectedIndex === null || this.selectedIndex === i ? col : withAlpha(col, 0.3),
    );
    return {
      type: 'doughnut',
      data: {
        labels,
        datasets: [
          {
            label: this.valueKey,
            data: values,
            backgroundColor: faded,
            borderColor: c.surface,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        ...this.commonOptions(),
        cutout: '62%',
        layout: { padding: 6 },
        plugins: {
          legend: {
            // Side legend only where there's room for it beside the ring.
            position: (this.canvasEl?.nativeElement.parentElement?.clientWidth ?? 600) < 460 ? 'bottom' : 'right',
            labels: {
              color: c.ink,
              boxWidth: 10,
              boxHeight: 10,
              padding: 10,
              font: { size: 12 },
              generateLabels: (chart) =>
                labels.map((label, i) => ({
                  text: `${truncate(label, 22)}  ${formatPct(pcts[i])}`,
                  fillStyle: colors[i],
                  strokeStyle: colors[i],
                  fontColor: c.ink,
                  hidden: !chart.getDataVisibility(i),
                  index: i,
                })),
            },
          },
          tooltip: {
            ...this.baseTooltip(),
            callbacks: {
              label: (context) =>
                `${formatValue(Number(context.parsed), this.valueKey)} · ${formatPct(pcts[context.dataIndex])} del total`,
            },
          },
          annotation: { annotations: {} },
        },
      },
    };
  }

  private commonOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: prefersReducedMotion() ? 0 : ENTRY_ANIMATION_DURATION_MS,
        easing: 'easeOutQuart' as const,
      },
      onClick: (event: ChartEvent, elements: ActiveElement[]) => this.onChartClick(event, elements),
      onHover: (event: ChartEvent, elements: ActiveElement[]) => {
        const target = event.native?.target as HTMLElement | undefined;
        if (target) {
          target.style.cursor = elements.length ? 'pointer' : 'default';
        }
      },
    };
  }

  private renderChart(): void {
    const canvas = this.canvasEl?.nativeElement;
    if (!canvas || !this.categoryKey || !this.valueKey) {
      return;
    }
    this.rows = buildParetoRows(this.records, this.categoryKey, this.valueKey);

    const config =
      this.view === 'ranking'
        ? (this.rankingConfig() as unknown as ChartConfiguration)
        : this.view === 'dona'
          ? (this.donutConfig() as unknown as ChartConfiguration)
          : (this.paretoConfig() as unknown as ChartConfiguration);

    // Same chart type -> update in place (animated transition, one instance).
    // A different type (bar <-> doughnut, or horizontal <-> vertical) can't
    // be morphed by Chart.js, so the old instance is destroyed first - never
    // two charts on one canvas.
    if (this.chart && this.chartView === this.view) {
      this.chart.data = config.data;
      this.chart.options = config.options ?? {};
      this.chart.update();
      return;
    }
    this.chart?.destroy();
    this.chartView = this.view;
    this.chart = new Chart(canvas, {
      ...config,
      plugins: [this.surfacePlugin(), this.barEndLabelsPlugin() as Plugin, this.centerTotalPlugin() as Plugin],
    });
  }
}
