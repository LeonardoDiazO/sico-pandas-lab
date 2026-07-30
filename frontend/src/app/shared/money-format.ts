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
  if (!columnName) {
    return false;
  }
  const lowered = columnName.toLowerCase();
  return MONEY_KEYWORDS.some((keyword) => lowered.includes(keyword));
}
