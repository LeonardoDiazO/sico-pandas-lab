import { Component, ElementRef, Input, OnChanges, SimpleChanges, ViewChild } from '@angular/core';

import { AnalysisBlock } from '../../models/api.models';
import { ChartCanvasComponent, ChartView } from '../chart-canvas/chart-canvas.component';
import { buildParetoRows, formatPct, formatValue, ParetoRow } from '../pareto-data';

export type BlockView = ChartView | 'tabla';

export interface ViewOption {
  value: BlockView;
  label: string;
  hint: string;
}

export const BLOCK_VIEWS: ViewOption[] = [
  { value: 'pareto', label: 'Pareto', hint: 'Barras + % acumulado: dónde se cruza el 80%' },
  { value: 'ranking', label: 'Ranking', hint: 'De mayor a menor, con nombres completos' },
  { value: 'dona', label: 'Participación', hint: 'Qué porción del total es cada una' },
  { value: 'tabla', label: 'Tabla', hint: 'Los números exactos' },
];

/**
 * One card of the automatic dashboard: a single dimension x métrica Pareto,
 * explorable in place. The same normalized rows (pareto-data.ts) feed every
 * view, the table, and the selection readout, so switching views never
 * changes a number. `defaultView` comes from the dashboard-wide "ver todas
 * como" control; picking a view on the card overrides it for that card only
 * until the global control changes again.
 */
@Component({
  selector: 'app-analysis-block',
  standalone: false,
  templateUrl: './analysis-block.component.html',
  styleUrl: './analysis-block.component.scss',
})
export class AnalysisBlockComponent implements OnChanges {
  @Input({ required: true }) bloque!: AnalysisBlock;
  @Input() defaultView: BlockView = 'pareto';

  @ViewChild('cardChart') private cardChart?: ChartCanvasComponent;
  @ViewChild('bigChart') private bigChart?: ChartCanvasComponent;
  @ViewChild('dialogEl') private dialogEl?: ElementRef<HTMLDialogElement>;

  readonly views = BLOCK_VIEWS;
  readonly formatValue = formatValue;
  readonly formatPct = formatPct;

  view: BlockView = 'pareto';
  topN: number | null = null;
  selectedIndex: number | null = null;
  rows: ParetoRow[] = [];
  expanded = false;
  readonly uid = `blk-${Math.random().toString(36).slice(2, 9)}`;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['defaultView']) {
      this.view = this.defaultView;
    }
    if (changes['bloque']) {
      this.rows = buildParetoRows(this.records, this.bloque.dimension, this.bloque.metrica);
      this.selectedIndex = null;
      // More than 10 bars stop being individually readable in a card.
      this.topN = this.rows.length > 10 ? 10 : null;
    }
  }

  get records(): Record<string, unknown>[] {
    return this.bloque?.resultado?.result_records ?? [];
  }

  get hasData(): boolean {
    return !this.bloque.resultado.error && this.rows.length > 0;
  }

  get vitalCount(): number {
    return this.rows.filter((r) => r.vital).length;
  }

  get total(): number {
    return this.rows.reduce((sum, r) => (Number.isFinite(r.value) ? sum + r.value : sum), 0);
  }

  get leader(): ParetoRow | null {
    return this.rows[0] ?? null;
  }

  get selectedRow(): ParetoRow | null {
    return this.selectedIndex === null ? null : (this.rows[this.selectedIndex] ?? null);
  }

  get hiddenCount(): number {
    return this.topN && this.view !== 'dona' && this.view !== 'tabla' ? Math.max(this.rows.length - this.topN, 0) : 0;
  }

  get topNOptions(): { value: number | null; label: string }[] {
    const opts: { value: number | null; label: string }[] = [];
    for (const n of [5, 10]) {
      if (this.rows.length > n) {
        opts.push({ value: n, label: `Top ${n}` });
      }
    }
    opts.push({ value: null, label: `Todas (${this.rows.length})` });
    return opts;
  }

  get chartView(): ChartView {
    return this.view === 'tabla' ? 'pareto' : this.view;
  }

  // Ranking grows with its bar count so every category name stays legible.
  rankingHeight(limit: number | null): number {
    const count = limit ? Math.min(limit, this.rows.length) : this.rows.length;
    return Math.max(180, Math.min(count * 30 + 40, 520));
  }

  setView(view: BlockView): void {
    this.view = view;
  }

  // Arrow-key roving across the segmented control (radio-group semantics).
  onViewKeydown(event: KeyboardEvent, index: number): void {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (!step) {
      return;
    }
    event.preventDefault();
    const next = (index + step + this.views.length) % this.views.length;
    this.view = this.views[next].value;
    const group = (event.currentTarget as HTMLElement).parentElement;
    queueMicrotask(() => (group?.children[next] as HTMLElement | undefined)?.focus());
  }

  select(index: number | null): void {
    this.selectedIndex = index === this.selectedIndex ? null : index;
  }

  barWidth(row: ParetoRow): number {
    const max = this.leader && Number.isFinite(this.leader.value) && this.leader.value > 0 ? this.leader.value : 1;
    return Number.isFinite(row.value) ? Math.max((row.value / max) * 100, 0) : 0;
  }

  // Fits short laptop screens: header + padding take ~220px of the dialog.
  get dialogChartHeight(): number {
    const h = typeof window !== 'undefined' ? window.innerHeight : 900;
    return Math.max(280, Math.min(480, h - 230));
  }

  openExpanded(): void {
    this.expanded = true;
    // The dialog's chart is created only while open (no hidden canvases).
    queueMicrotask(() => this.dialogEl?.nativeElement.showModal());
  }

  closeExpanded(): void {
    this.dialogEl?.nativeElement.close();
  }

  onDialogClose(): void {
    this.expanded = false;
  }

  onDialogClick(event: MouseEvent): void {
    // A click on the backdrop lands on the <dialog> element itself.
    if (event.target === this.dialogEl?.nativeElement) {
      this.closeExpanded();
    }
  }

  downloadPng(): void {
    const chart = this.expanded ? this.bigChart : this.cardChart;
    const url = chart?.toPng();
    if (!url) {
      return;
    }
    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.bloque.titulo.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').toLowerCase() || 'grafica'}.png`;
    link.click();
  }

  downloadCsv(): void {
    const escape = (v: string) => (/[";\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const header = [this.bloque.dimension, this.bloque.metrica, '% del total', '% acumulado', 'Parte del 80%'];
    const lines = this.rows.map((r) =>
      [
        r.label,
        Number.isFinite(r.value) ? String(r.value).replace('.', ',') : '',
        r.pct.toFixed(1).replace('.', ','),
        r.cum.toFixed(1).replace('.', ','),
        r.vital ? 'Sí' : 'No',
      ]
        .map(escape)
        .join(';'),
    );
    // BOM + ";" separator: opens with accents and columns intact in Excel
    // configured for es-CO.
    const blob = new Blob(['﻿' + [header.map(escape).join(';'), ...lines].join('\r\n')], {
      type: 'text/csv;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.bloque.titulo.replace(/[^\p{L}\p{N}]+/gu, '-').toLowerCase()}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
