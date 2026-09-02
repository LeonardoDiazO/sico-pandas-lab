// User feedback (real file: "detallado comfenalco"): a money column (neto,
// valor total, costo...) needs a "$" sign and Colombian-style "." thousands
// separator to actually read as currency - a plain quantity column (Cant,
// Consec) must NOT get a "$" prefix. The Excel profiler has no concept of
// "this numeric column is money" (it only classifies categorica/numerica/
// fecha/descartable), so this is a substring heuristic on the column name -
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

export function looksLikeMoney(columnName: string | null | undefined): boolean {
  // Real bug report (file: "relacion de facturas matecol.xlsx"): its own
  // value column is literally named "N E T O" - one letter per cell joined
  // with spaces (a two-row split header in that report). Stripping ALL
  // whitespace before matching (not just trimming the ends) fixes this
  // generically - no keyword above contains a space itself, so this can
  // only turn a previously-missed match into a correct one, never the
  // reverse. Same fix as backend/app/notebook/chart_builder.py's
  // _looks_like_money() - keep both in sync.
  if (!columnName) {
    return false;
  }
  const lowered = columnName.toLowerCase().replace(/\s+/g, '');
  // Real bug found in production: a merged two-row header column named
  // "Cantidad Venta" (a UNIT COUNT, not a peso amount) got a "$" prefix
  // because "venta" alone is a money keyword - "venta" is genuinely
  // ambiguous in Spanish ("the sale" as an event/count vs. its peso value).
  // "cantidad" (quantity) is an unambiguous negative signal that overrides
  // any positive keyword match - same fix and same one-directional safety
  // as backend/app/notebook/chart_builder.py's _looks_like_money() - keep
  // both in sync.
  if (lowered.includes('cantidad')) {
    return false;
  }
  return MONEY_KEYWORDS.some((keyword) => lowered.includes(keyword));
}
