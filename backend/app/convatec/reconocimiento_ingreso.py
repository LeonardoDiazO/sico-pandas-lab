"""Story request (2026-08-06): validate the processed cycle's grand total
against the SAP "Reconocimiento de Ingresos" journal entry export -- step 10
of John's original process ("Validación de cifras comparativo SAP
Hyperion"). This file is NOT an assignment input: it has no Convenio,
Codigo or Departamento, so it never goes through pipeline.py -- its only
role is a total-vs-total sanity check after processing.

Real file inspected during manual review: a legacy .xls SAP GL export with
6 metadata rows, then a header row, then one row per journal-entry line.
"Credit amount" (posting key 50) carries the per-product-line revenue
recognition value -- the side comparable to our own per-line Valor Total.
"Debit amount" (posting key 9) is an aggregated clearing/receivable entry
grouped differently (117 rows vs 280 credit rows in the sample file), not
comparable line-for-line -- but both sides sum to the same grand total in a
balanced journal, so either works for a total-only check; Credit amount is
used since it is the semantically correct side.
"""
import pandas as pd

HEADER_ROW = 8  # 0-indexed; Excel row 9 in the real template


class ReconocimientoIngresoError(ValueError):
    """Raised when the uploaded workbook doesn't look like the expected SAP export."""


def _engine_for(file_storage) -> str:
    filename = (getattr(file_storage, "filename", "") or "").lower()
    if filename.endswith(".xls"):
        return "xlrd"
    if filename.endswith(".xlsx"):
        return "openpyxl"
    raise ReconocimientoIngresoError("El archivo debe ser un Excel (.xls o .xlsx).")


def load_total_reconocimiento(file_storage) -> float:
    """Returns the grand total (Credit amount column) of the uploaded
    Reconocimiento de Ingresos export."""
    engine = _engine_for(file_storage)
    if hasattr(file_storage, "seek"):
        file_storage.seek(0)
    try:
        df = pd.read_excel(file_storage, header=HEADER_ROW, engine=engine)
    except ReconocimientoIngresoError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ReconocimientoIngresoError(f"No se pudo leer el Excel: {exc}") from exc

    if "Credit amount" not in df.columns:
        raise ReconocimientoIngresoError(
            "El Excel no tiene la columna 'Credit amount' esperada del reporte de reconocimiento de ingresos."
        )
    return float(df["Credit amount"].sum())
