"""Parse an uploaded Excel file into a pandas DataFrame.

Runs in the Flask process (not the worker) and returns a plain DataFrame that
the caller binds into the session namespace. Kept tiny and dependency-light so
it is easy to test.
"""
import pandas as pd


def load_excel_dataframe(file_storage):
    """Read a werkzeug FileStorage (.xlsx) into a DataFrame.

    Raises ValueError with a user-friendly message on anything that is not a
    readable Excel file, so the route can surface a clean error without the
    session breaking.
    """
    filename = (getattr(file_storage, "filename", "") or "").lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise ValueError("El archivo debe ser un Excel (.xlsx o .xls).")
    try:
        return pd.read_excel(file_storage, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc
