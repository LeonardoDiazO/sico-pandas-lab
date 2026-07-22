"""Profile an uploaded Excel file: detect the real header row, infer a type
per column, and produce a usability verdict.

Wraps excel_loader.py rather than replacing it (reuses its extension/corrupt
-file validation via read_excel_raw()). Runs in the Flask request thread, not
inside the isolated per-session worker, so it stays fast by design instead of
relying on the worker's resource.setrlimit timeout: the header scan is capped
and no O(n^2) work is done over the full row count.
"""
import re
import warnings

import pandas as pd

from app.data_access.excel_loader import read_excel_raw

MAX_HEADER_SCAN_ROWS = 30
HEADER_LOOKAHEAD_ROWS = 10
DATA_WIDTH_RATIO = 0.85
WINDOW_DENSE_RATIO = 0.65
NUMERIC_ROW_RATIO = 0.4
JUNK_ROW_WIDTH_RATIO = 0.5
JUNK_TEXT_PATTERN = re.compile(r"\bSUBTOTAL\b|\bTOTALES?\b|\bTOT\.", re.IGNORECASE)
NUMERIC_MIN_RATIO = 0.9
CARDINALITY_MEASURE_RATIO = 0.5
DATE_MIN_RATIO = 0.9
DATE_YYYYMMDD_PATTERN = re.compile(r"^(19|20)\d{6}$")
DATE_SEPARATOR_PATTERN = re.compile(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}$")

VERDICT_USABLE = "usable"
VERDICT_USABLE_CON_LIMPIEZA = "usable_con_limpieza"
VERDICT_NO_USABLE = "no_usable"

TYPE_CATEGORICA = "categorica"
TYPE_NUMERICA = "numerica"
TYPE_FECHA = "fecha"
TYPE_DESCARTABLE = "descartable"


def profile_excel(file_storage):
    """Read, profile and verdict an uploaded Excel file.

    Returns a plain dict:
    {"verdict": str, "header_row_index": int|None, "columns": [{"name", "type"}],
     "detail": str, "dataframe": pd.DataFrame|None}
    "dataframe" is the already-cleaned table (header applied, junk rows dropped) —
    None whenever verdict is "no_usable", since there's nothing usable to bind.
    Internal-only: callers must not leak it verbatim into an HTTP response.
    Raises ValueError (via read_excel_raw) for a missing/wrong-extension/corrupt file.
    """
    raw = read_excel_raw(file_storage)

    header_row_index = _detect_header_row(raw)
    if header_row_index is None:
        return {
            "verdict": VERDICT_NO_USABLE,
            "header_row_index": None,
            "columns": [],
            "detail": (
                "No se encontró una tabla de datos reconocible en las primeras filas "
                "del archivo. Revisa que el Excel tenga una fila de encabezado y datos debajo."
            ),
            "dataframe": None,
        }

    header = raw.iloc[header_row_index]
    data = raw.iloc[header_row_index + 1 :].reset_index(drop=True)
    data.columns = _dedupe_names(
        str(value).strip() if pd.notna(value) and str(value).strip() else f"col_{i}"
        for i, value in enumerate(header)
    )

    junk_mask = _compute_junk_mask(data)
    clean_rows = data.loc[~junk_mask].reset_index(drop=True)

    columns = _infer_column_types(clean_rows)
    clean_rows = _coerce_numeric_columns(clean_rows, columns)

    if not any(c["type"] in (TYPE_CATEGORICA, TYPE_NUMERICA) for c in columns):
        return {
            "verdict": VERDICT_NO_USABLE,
            "header_row_index": header_row_index,
            "columns": columns,
            "detail": (
                "El archivo tiene una fila de encabezado, pero ninguna columna con datos "
                "de categoría o números reconocibles para graficar."
            ),
            "dataframe": None,
        }

    junk_row_count = int(junk_mask.sum())
    needs_cleanup = header_row_index > 0 or junk_row_count > 0

    if needs_cleanup:
        verdict = VERDICT_USABLE_CON_LIMPIEZA
        detail = (
            f"Se detectó el encabezado en la fila {header_row_index + 1} del archivo "
            f"y se identificaron {junk_row_count} filas que no son datos reales "
            "(metadata, subtotales o filas vacías) — se pueden filtrar antes de graficar."
        )
    else:
        verdict = VERDICT_USABLE
        detail = "El archivo tiene una fila de encabezado clara y todas las filas siguientes son datos."

    return {
        "verdict": verdict,
        "header_row_index": header_row_index,
        "columns": columns,
        "detail": detail,
        "dataframe": clean_rows,
    }


def _detect_header_row(raw):
    """Find the row carrying the real column labels.

    Two passes, both capped at MAX_HEADER_SCAN_ROWS/HEADER_LOOKAHEAD_ROWS for
    speed:

    1. Find where the dense data block reliably begins: the "typical data
       width" (mode of non-null cell counts across the sheet) approximates
       how many columns a real data row fills; we look for the first row
       after which most of the next several rows are that wide. A plain
       "require every row in the window dense" check breaks on real reports
       where blank/subtotal rows interrupt the data block every few rows
       (e.g. a subtotal line every N invoices) — using a ratio tolerates that.
    2. Reports with a header split across two lines (a broad category row
       or fully blank spacer, then the specific field-name row) mean the
       boundary from step 1 can land one or two rows before the row that
       actually has usable labels. From the boundary, walk forward through
       consecutive "mostly text, not mostly numeric" rows — the last one
       right before a row that's mostly numeric (an actual data row) is the
       real header.
    """
    n_rows = len(raw)
    if n_rows == 0:
        return None

    non_null_counts = raw.notna().sum(axis=1)

    # "typical width" is estimated from a LOCAL sample - the same bounded
    # range (MAX_HEADER_SCAN_ROWS + HEADER_LOOKAHEAD_ROWS) the rest of this
    # function already scans - rather than the GLOBAL mode across the whole
    # file. A real report's data body can start out sparser than its
    # steady-state further down (optional fields only populated later);
    # using the global mode as "typical width" required a density the
    # file's own early rows might never reach, wrongly rejecting files with
    # a perfectly valid header and data.
    sample_end = min(MAX_HEADER_SCAN_ROWS + HEADER_LOOKAHEAD_ROWS, n_rows)
    local_counts = non_null_counts.iloc[:sample_end]
    width_counts = local_counts.mode()
    if width_counts.empty or width_counts.max() == 0:
        return None
    # On a tie (e.g. a sparse metadata preamble and the real header+data
    # rows evenly splitting the local window), prefer the WIDER candidate:
    # real data rows fill more columns than metadata/label rows, so the
    # wider mode is the more reliable proxy for "typical data width" -
    # mode() sorts ascending, so the narrower (wrong) candidate would win if
    # this just took the first entry.
    typical_width = width_counts.max()
    dense_threshold = typical_width * DATA_WIDTH_RATIO

    scan_limit = min(MAX_HEADER_SCAN_ROWS, n_rows)
    boundary_start = None
    for row_idx in range(scan_limit):
        window_end = min(row_idx + 1 + HEADER_LOOKAHEAD_ROWS, n_rows)
        window = non_null_counts.iloc[row_idx + 1 : window_end]
        if len(window) == 0:
            continue
        if (window >= dense_threshold).mean() >= WINDOW_DENSE_RATIO:
            boundary_start = row_idx
            break
    if boundary_start is None:
        return None

    header_row_index = None
    scan_end = min(boundary_start + HEADER_LOOKAHEAD_ROWS + 1, n_rows)
    for row_idx in range(boundary_start, scan_end):
        non_null = raw.iloc[row_idx].dropna()
        if len(non_null) == 0:
            continue
        numeric_fraction = pd.to_numeric(non_null, errors="coerce").notna().mean()
        if numeric_fraction >= NUMERIC_ROW_RATIO:
            break  # first row that looks like actual data - stop here
        header_row_index = row_idx
    # If the very first candidate row is already data-like, there was never a
    # text header to find (e.g. a raw numeric dump) - report "no header" rather
    # than silently treating a data row's values as column names.
    return header_row_index


def _compute_junk_mask(data):
    """Vectorized "is this row empty/mostly-empty/a totals marker" check.

    Unlike header detection (capped at MAX_HEADER_SCAN_ROWS), this runs over
    every row of the uploaded file's data body, so a Python-level per-row loop
    here would scale with file size in the request thread - stays vectorized
    (pandas/numpy C-level ops) instead.
    """
    non_null_counts = data.notna().sum(axis=1)
    width_mask = non_null_counts < (data.shape[1] * JUNK_ROW_WIDTH_RATIO)
    text_mask = data.astype(str).apply(lambda col: col.str.contains(JUNK_TEXT_PATTERN, na=False)).any(axis=1)
    return width_mask | text_mask


def _dedupe_names(names):
    """Real-world reports reuse a label across merged/split header cells
    (e.g. two columns both literally called "Cliente") — suffix repeats so
    every column name is unique, same convention pandas itself uses.
    """
    seen = {}
    result = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
    return result


def _coerce_numeric_columns(data, columns):
    """Restore real numeric dtype for columns classified "numerica".

    `read_excel_raw` reads with header=None, so every raw column mixes the
    text header cell with the data cells before this module slices the header
    off - pandas then infers `object` dtype for the whole column instead of
    float64/int64. Left uncorrected, `df.describe()`/`select_dtypes` silently
    stop recognizing these columns as numeric for every bound upload, not
    just messy ones. "fecha" columns are deliberately left as-is: the guided
    lesson has the user convert them with `pd.to_datetime` themselves.
    """
    numeric_names = {c["name"] for c in columns if c["type"] == TYPE_NUMERICA}
    for name in numeric_names:
        data[name] = pd.to_numeric(data[name], errors="coerce")
    return data


def _infer_column_types(data):
    columns = []
    for position in range(data.shape[1]):
        name = data.columns[position]
        series = data.iloc[:, position].dropna()
        if len(series) == 0:
            columns.append({"name": name, "type": TYPE_DESCARTABLE})
            continue

        # Date check first: a YYYYMMDD-style date (e.g. 20260701) is also
        # valid numeric data, so numeric alone can't tell them apart - dates
        # are the more specific/useful classification for grouping/plotting.
        if _is_date_like(series):
            columns.append({"name": name, "type": TYPE_FECHA})
            continue

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().mean() >= NUMERIC_MIN_RATIO:
            column_type = TYPE_NUMERICA if _looks_like_numeric_measure(numeric) else TYPE_CATEGORICA
            columns.append({"name": name, "type": column_type})
            continue

        columns.append({"name": name, "type": TYPE_CATEGORICA})
    return columns


def _looks_like_numeric_measure(numeric):
    """A fully-numeric column can still be a category in disguise (vendor
    codes, warehouse codes, NIT numbers - see GUIA_PRACTICA_FACTURAS_MATECOL.md
    section 6, which explicitly casts 'vdor'/'bod' back to text because
    "no tiene sentido sumar códigos de vendedor"). Two signals distinguish a
    real measure from a numeric-looking code: it has decimal values (codes
    are always whole numbers), or its values are mostly distinct (a measure
    varies per row; a code repeats across many rows sharing that group).
    """
    values = numeric.dropna()
    if len(values) == 0:
        return True
    has_decimals = ((values % 1) != 0).mean() > 0.1
    if has_decimals:
        return True
    cardinality_ratio = values.nunique() / len(values)
    return cardinality_ratio >= CARDINALITY_MEASURE_RATIO


def _is_date_like(series):
    """Cheap YYYYMMDD check first; only fall back to pd.to_datetime (slower,
    dateutil-based) when values actually look date-shaped, so plain short
    codes (e.g. vendor ids like "0", "1") never trigger the slow path.
    """
    as_str = series.astype(str).str.strip()
    yyyymmdd_ratio = as_str.str.match(DATE_YYYYMMDD_PATTERN).mean()
    if yyyymmdd_ratio >= DATE_MIN_RATIO:
        return True
    separator_ratio = as_str.str.match(DATE_SEPARATOR_PATTERN).mean()
    if separator_ratio < DATE_MIN_RATIO:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(series, errors="coerce")
    return parsed.notna().mean() >= DATE_MIN_RATIO
