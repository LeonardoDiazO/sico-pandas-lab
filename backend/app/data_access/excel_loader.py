"""Parse an uploaded Excel file into a pandas DataFrame.

Runs in the Flask process (not the worker) and returns a plain DataFrame that
the caller binds into the session namespace. Kept tiny and dependency-light so
it is easy to test.
"""
import pandas as pd


def _validate_and_rewind(file_storage):
    """Check the extension and rewind the stream so callers can read fresh.

    Rewinding here means excel_profiler and this module can both read the
    same upload (profile then load) without the route managing seek() itself.
    """
    filename = (getattr(file_storage, "filename", "") or "").lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise ValueError("El archivo debe ser un Excel (.xlsx o .xls).")
    if hasattr(file_storage, "seek"):
        file_storage.seek(0)


def load_excel_dataframe(file_storage):
    """Read a werkzeug FileStorage (.xlsx) into a DataFrame.

    Raises ValueError with a user-friendly message on anything that is not a
    readable Excel file, so the route can surface a clean error without the
    session breaking.
    """
    _validate_and_rewind(file_storage)
    try:
        return pd.read_excel(file_storage, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc


def read_excel_raw(file_storage):
    """Read a werkzeug FileStorage (.xlsx) with no assumed header row.

    Used by excel_profiler to inspect the raw grid (row 0 is just data, not
    column names) before deciding where the real header actually is.
    """
    _validate_and_rewind(file_storage)
    try:
        return pd.read_excel(file_storage, engine="openpyxl", header=None)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc
