"""Parse the "Tables" sheet of Convatec's master-tables workbook.

The sheet lays out ~17 reference tables side by side on the same grid: a
table-name label two rows above a header row, then data rows underneath,
until the next table's label starts. This locates each table by its label
instead of hardcoding column numbers, so a table sliding a column or two
(a maestro re-export, a new blank spacer column) doesn't silently break the
parser.

Only PRODUCTO, REPRESENTANTES and CONVENIOS are extracted -- the only three
of the 17 tables the assignment engine actually consumes (Regla 2 uses
REPRESENTANTES directly, FR-5's Convenio->Ciudad resolution uses CONVENIOS;
Reglas 1/3, "Repartir" and directrices come from app.convatec.reference_data,
see that module's docstring for why).
"""
import pandas as pd

TABLE_NAME_ROW = 1  # 0-indexed row holding table-name labels (Excel row 2)
HEADER_ROW = 3  # 0-indexed row holding column headers (Excel row 4)
DATA_START_ROW = 4  # 0-indexed first data row (Excel row 5)

REQUIRED_TABLES = ("PRODUCTO", "REPRESENTANTES", "CONVENIOS")


class MasterTablesError(ValueError):
    """Raised when the uploaded workbook doesn't look like the expected template."""


def _validate_extension(file_storage):
    filename = (getattr(file_storage, "filename", "") or "").lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise MasterTablesError("El archivo debe ser un Excel (.xlsx o .xls).")


def _read_tables_sheet(file_storage):
    _validate_extension(file_storage)
    if hasattr(file_storage, "seek"):
        file_storage.seek(0)
    try:
        raw = pd.read_excel(file_storage, sheet_name="Tables", header=None, engine="openpyxl")
    except ValueError as exc:
        raise MasterTablesError(
            "El Excel de tablas maestras debe tener una hoja llamada 'Tables'."
        ) from exc
    except MasterTablesError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise MasterTablesError(f"No se pudo leer el Excel de tablas maestras: {exc}") from exc

    if raw.shape[0] <= HEADER_ROW:
        raise MasterTablesError(
            "La hoja 'Tables' está vacía o incompleta (le faltan filas de encabezado)."
        )
    return raw


def _table_start_columns(raw):
    """Map table name -> starting column index, from the label row.

    The real workbook legitimately repeats a handful of table labels
    (PRODUCTOS CONVERSIÓN, CIUDAD, CONVENIOS CONSOLIDADO all appear twice at
    different column offsets -- confirmed by inspecting the actual file, not
    a malformed upload). Only a duplicate among REQUIRED_TABLES -- the ones
    this module actually reads -- is ambiguous enough to reject; for any
    other repeated label, the first occurrence is kept and the rest ignored.
    """
    label_row = raw.iloc[TABLE_NAME_ROW]
    starts: dict[str, int] = {}
    for col_idx, value in enumerate(label_row):
        if isinstance(value, str) and value.strip():
            name = value.strip().upper()
            if name in starts:
                if name in REQUIRED_TABLES:
                    raise MasterTablesError(
                        f"La tabla '{name}' aparece más de una vez en la fila de nombres de tabla."
                    )
                continue
            starts[name] = col_idx
    return starts


def _extract_table(raw, table_name, start_col, next_start_col):
    """Slice one table's columns/rows out of the raw grid and name its columns."""
    end_col = next_start_col if next_start_col is not None else raw.shape[1]
    headers = raw.iloc[HEADER_ROW, start_col:end_col].tolist()
    block = raw.iloc[DATA_START_ROW:, start_col:end_col].copy()
    block.columns = [str(h).strip() if pd.notna(h) else f"_col{i}" for i, h in enumerate(headers)]
    # Drop spacer columns (no header) and rows that are entirely blank -- the
    # sheet pads every table's column block to a fixed width so the next
    # table starts on a clean offset.
    block = block.loc[:, [c for c in block.columns if not c.startswith("_col")]]
    block = block.dropna(how="all")
    if block.empty:
        raise MasterTablesError(f"La tabla '{table_name}' no tiene filas de datos.")
    return block.reset_index(drop=True)


def load_master_tables(file_storage):
    """Parse the uploaded workbook into {table_name: DataFrame} for PRODUCTO,
    REPRESENTANTES and CONVENIOS.

    Raises MasterTablesError with a user-facing message if the workbook is
    missing the 'Tables' sheet or any required table.
    """
    raw = _read_tables_sheet(file_storage)
    starts = _table_start_columns(raw)

    missing = [name for name in REQUIRED_TABLES if name not in starts]
    if missing:
        raise MasterTablesError(
            "El Excel de tablas maestras no tiene las tablas requeridas: " + ", ".join(missing)
        )

    ordered_starts = sorted(starts.items(), key=lambda kv: kv[1])
    next_start = {
        name: (ordered_starts[i + 1][1] if i + 1 < len(ordered_starts) else None)
        for i, (name, _col) in enumerate(ordered_starts)
    }

    return {
        name: _extract_table(raw, name, starts[name], next_start[name])
        for name in REQUIRED_TABLES
    }
