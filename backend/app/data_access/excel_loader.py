"""Parse an uploaded Excel file into a pandas DataFrame.

Runs in the Flask process (not the worker) and returns a plain DataFrame that
the caller binds into the session namespace. Kept tiny and dependency-light so
it is easy to test.
"""
import pandas as pd

# The two real container formats a ".xls"/".xlsx" upload can actually be,
# identified by their own file signature - never by the filename extension.
# A real production file (est_proveedorvdart_admon.xls) turned out to be a
# modern XLSX/OOXML file some ERP just exported with a ".xls" extension; a
# genuine legacy Excel 97-2003 file is the OTHER real shape, an OLE2/BIFF
# binary. Trusting the extension alone picks the wrong engine for whichever
# shape doesn't match it - openpyxl (OOXML-only) raises a confusing
# "BadZipFile: File is not a zip file" on a real legacy .xls, even though
# xlrd (which reads exactly that format) is already a project dependency and
# was simply never wired in.
_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_SIGNATURE = b"PK\x03\x04"


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


def _detect_engine(file_storage):
    """Picks the pandas engine from the file's own signature, not its name -
    see the module docstring for why the extension alone can't be trusted
    either way. Defaults to openpyxl for anything that isn't recognizably
    OLE2 (including a genuinely corrupt file) - it already raises a clear
    enough error for that case, and openpyxl is the more common real shape
    for a file with either extension in practice.
    """
    header = file_storage.read(8)
    if hasattr(file_storage, "seek"):
        file_storage.seek(0)
    if header.startswith(_OLE2_SIGNATURE):
        return "xlrd"
    return "openpyxl"


def load_excel_dataframe(file_storage):
    """Read a werkzeug FileStorage (.xlsx or legacy .xls) into a DataFrame.

    Raises ValueError with a user-friendly message on anything that is not a
    readable Excel file, so the route can surface a clean error without the
    session breaking.
    """
    _validate_and_rewind(file_storage)
    engine = _detect_engine(file_storage)
    try:
        return pd.read_excel(file_storage, engine=engine)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc


def read_excel_raw(file_storage):
    """Read a werkzeug FileStorage (.xlsx or legacy .xls) with no assumed
    header row.

    Used by excel_profiler to inspect the raw grid (row 0 is just data, not
    column names) before deciding where the real header actually is.
    """
    _validate_and_rewind(file_storage)
    engine = _detect_engine(file_storage)
    try:
        return pd.read_excel(file_storage, engine=engine, header=None)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc
