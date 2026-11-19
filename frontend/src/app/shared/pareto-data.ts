import { looksLikeMoney, parseMoneyValue } from './money-format';

/**
 * One normalized row of a Pareto summary (table_builder.py's
 * build_summary_code output, as `result_records`). Every consumer in the
 * automatic dashboard - the canvas chart in all its views, the table view,
 * the selection readout - reads from this one shape, so they can never
 * disagree on a value, a percentage, or which rows are "the 80%".
 */
export interface ParetoRow {
  label: string;
  value: number;
  pct: number;
  cum: number;
  // True for the rows that together reach the 80% crossing (the "vital
  // few"), including the crossing row itself - same rule as the backend's
  // _pareto_marker_lines ✓ marks.
  vital: boolean;
}

export function toNumber(raw: unknown): number {
  if (typeof raw === 'number') {
    return raw;
  }
  if (typeof raw === 'string') {
    return parseMoneyValue(raw);
  }
  return NaN;
}

/**
 * Normalizes result_records into ParetoRows. '% del total' / '% acumulado'
 * come from the backend when present (they are the numbers the printed
 * insight sentence was computed from); when a record set lacks them they are
 * derived here from the values, so the views still work for any
 * category+value table.
 */
export function buildParetoRows(
  records: Record<string, unknown>[] | null | undefined,
  categoryKey: string,
  valueKey: string,
): ParetoRow[] {
  if (!records?.length || !categoryKey || !valueKey) {
    return [];
  }
  const values = records.map((r) => toNumber(r[valueKey]));
  const total = values.reduce((sum, v) => (Number.isFinite(v) ? sum + v : sum), 0);
  let running = 0;
  const rows = records.map((record, i) => {
    const value = values[i];
    const pctRaw = toNumber(record['% del total']);
    const pct = Number.isFinite(pctRaw) ? pctRaw : total ? ((Number.isFinite(value) ? value : 0) / total) * 100 : 0;
    const cumRaw = toNumber(record['% acumulado']);
    running += pct;
    const cum = Number.isFinite(cumRaw) ? cumRaw : running;
    return { label: String(record[categoryKey] ?? '(vacío)'), value, pct, cum, vital: false };
  });
  // Vital = every row before the first one at/over 80%, plus that row.
  const crossing = rows.findIndex((r) => r.cum >= 80);
  const lastVital = crossing === -1 ? rows.length - 1 : crossing;
  rows.forEach((r, i) => (r.vital = i <= lastVital));
  return rows;
}

export function formatValue(value: number, valueKey: string): string {
  if (!Number.isFinite(value)) {
    return 'sin dato';
  }
  if (looksLikeMoney(valueKey)) {
    return `$ ${Math.round(value).toLocaleString('es-CO')}`;
  }
  return value.toLocaleString('es-CO', { maximumFractionDigits: 2 });
}

/** Compact axis label: "$ 1,2 M" instead of "$ 1.234.567" on a tick. */
export function formatCompact(value: number, valueKey: string): string {
  if (!Number.isFinite(value)) {
    return '';
  }
  const compact = new Intl.NumberFormat('es-CO', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
  return looksLikeMoney(valueKey) ? `$ ${compact}` : compact;
}

export function formatPct(value: number): string {
  return `${Number.isFinite(value) ? value.toLocaleString('es-CO', { maximumFractionDigits: 1 }) : '0'}%`;
}
