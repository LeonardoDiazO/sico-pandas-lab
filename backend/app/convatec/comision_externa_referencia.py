"""Parses "COMISION POR VENTAS.xls" -- confirmed during manual review (and
by the user directly) to be from a different client/system, NOT Convatec:
its vendor ("VEGA BELEÑO CARLOS") and structure (warehouse "Bod", "Salidas x
Ventas") match no table in Convatec's real master data. It has no Convenio,
Codigo or Departamento, so -- like reconocimiento_ingreso.py -- it can never
reach pipeline.py.

Explicit user decision (2026-08-06): still surface it, but only as a
disconnected reference table (its own vendor/tasa/neto/comision, aggregated
per vendor) -- never presented as, or mixed with, Convatec data. The UI is
responsible for the "no es de Convatec" label; this module only parses.
"""
import pandas as pd

HEADER_ROW = 6  # 0-indexed; Excel row 7 in the real template
_EXCLUDED_VENDEDOR_PREFIXES = ("SUBTOTAL", "TOTALES")


class ComisionExternaError(ValueError):
    """Raised when the uploaded workbook doesn't look like the expected export."""


def _engine_for(file_storage) -> str:
    filename = (getattr(file_storage, "filename", "") or "").lower()
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        # The real file is a zip/xlsx payload saved with a legacy .xls
        # extension (confirmed by inspecting its bytes) -- openpyxl handles
        # both cases correctly since it validates by content, not by name.
        return "openpyxl"
    raise ComisionExternaError("El archivo debe ser un Excel (.xls o .xlsx).")


def load_comision_externa(file_storage, sheet_name: str = "Hoja2") -> list[dict]:
    """Returns one row per vendedor: {vendedor, neto, porcentaje, comision}
    (Neto and Comision summed across that vendor's invoices)."""
    engine = _engine_for(file_storage)
    if hasattr(file_storage, "seek"):
        file_storage.seek(0)
    try:
        df = pd.read_excel(file_storage, sheet_name=sheet_name, header=HEADER_ROW, engine=engine)
    except ComisionExternaError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ComisionExternaError(f"No se pudo leer el Excel: {exc}") from exc

    required = ["Vendedor", "N E T O", "Com", "Comision"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ComisionExternaError(
            "El Excel no tiene las columnas esperadas de este reporte: " + ", ".join(missing)
        )

    detalle = df[df["Vendedor"].notna()]
    detalle = detalle[~detalle["Vendedor"].astype(str).str.upper().str.startswith(_EXCLUDED_VENDEDOR_PREFIXES)]

    resumen = detalle.groupby("Vendedor", as_index=False).agg(
        neto=("N E T O", "sum"),
        porcentaje=("Com", "first"),
        comision=("Comision", "sum"),
    )
    return [
        {
            "vendedor": row["Vendedor"],
            "neto": float(row["neto"]),
            "porcentaje": float(row["porcentaje"]),
            "comision": float(row["comision"]),
        }
        for _, row in resumen.iterrows()
    ]
