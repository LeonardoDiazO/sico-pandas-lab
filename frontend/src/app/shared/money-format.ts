// User feedback (real file: "detallado comfenalco"): a money column (neto,
// valor total, costo...) needs a "$" sign and Colombian-style "." thousands
// separator to actually read as currency - a plain quantity column (Cant,
// Consec) must NOT get a "$" prefix. The Excel profiler has no concept of
// "this numeric column is money" (it only classifies categorica/numerica/
// fecha/descartable), so this is a word heuristic on the column name -
// imperfect but good enough without asking the user to tag every column.
//
// Duplicated in backend/app/notebook/chart_builder.py's _MONEY_KEYWORDS (no
// shared module between the Python backend and the TypeScript frontend) -
// keep both keyword lists in sync if this one changes.
const MONEY_KEYWORDS = [
  'valor',
  'venta',
  'costo',
  'neto',
  'precio',
  'monto',
  'pago',
  'saldo',
  'ingreso',
  'egreso',
  'factura',
  'flete',
  'descuento',
  'iva',
  'bruto',
  'importe',
  'subtotal',
];

const NEGATIVE_MONEY_TOKENS = new Set(['cantidad', 'cantidades']);

function stripAccents(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '');
}

// Splits a column name into lower-case words: separators (spaces, _, -, .,
// /) and camelCase boundaries. A header spelled one letter per cell ("N E T
// O", "V A L O R   T O T A L") is re-joined: runs of single letters
// separated by single spaces become one word, and a name made only of single
// letters becomes one word. Same rules as chart_builder.py's _name_tokens().
export function nameTokens(columnName: string): string[] {
  const name = columnName
    .trim()
    .replace(/([a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])/g, '$1 ')
    // Letters glued to digits are separate words ("Venta2026").
    .replace(/([A-Za-zÀ-ÿ])(?=\d)|(\d)(?=[A-Za-zÀ-ÿ])/g, '$1$2 ');
  const groups = name.split(/\s{2,}/).filter((g) => g.length > 0);
  let words: string[] = [];
  for (const group of groups) {
    const pieces = group.split(' ');
    if (pieces.length > 1 && pieces.every((p) => p.length === 1)) {
      words.push(pieces.join(''));
    } else {
      // Any non-letter/digit run separates words ("Valor($)", "Neto:").
      words.push(...group.split(/[^0-9A-Za-zÀ-ÿ]+/));
    }
  }
  words = words.filter((w) => w.length > 0);
  if (words.length > 1 && words.every((w) => w.length === 1)) {
    words = [words.join('')];
  }
  return words.map((w) => stripAccents(w.toLowerCase()));
}

export function looksLikeMoney(columnName: string | null | undefined): boolean {
  // Decided per WORD of the column name, never by substring (auditoría
  // 2026-11-18: "Inventario" contains "venta" and "Clientes activa" contains
  // "iva", and both were shown as pesos). A keyword counts when it is a whole
  // word - exactly or in plural ("Ventas", "Valores"). "N E T O" style
  // headers are re-joined (nameTokens) and the word "cantidad" overrides any
  // money word ("Cantidad Venta" is a unit count). Same rules as
  // backend/app/notebook/chart_builder.py's _looks_like_money() - keep both
  // in sync.
  if (!columnName) {
    return false;
  }
  const tokens = nameTokens(columnName);
  if (tokens.some((t) => NEGATIVE_MONEY_TOKENS.has(t))) {
    return false;
  }
  return tokens.some((t) => MONEY_KEYWORDS.some((k) => t === k || t === `${k}s` || t === `${k}es`));
}

// A money-looking value column (see looksLikeMoney) arrives from the
// backend already formatted for display, not as a raw number - table_
// builder.py's _money_format_expr renders it as "$ 12.345" ("$ " prefix +
// "." thousands separators, no decimals). Anything that consumes those
// values numerically (e.g. chart-canvas.component.ts building a Chart.js
// dataset) needs to undo that formatting first. Kept here rather than
// inlined at each call site so this stays the single place money-format
// heuristics live, in sync with the backend.
export function parseMoneyValue(raw: string): number {
  const cleaned = raw.replace('$', '').replace(/\./g, '').trim();
  const parsed = Number(cleaned);
  // NaN (not 0) when it doesn't parse - Chart.js renders a gap for a NaN
  // data point instead of a misleading zero-height bar, and 0 would be
  // indistinguishable from a real zero value.
  return Number.isFinite(parsed) ? parsed : NaN;
}
