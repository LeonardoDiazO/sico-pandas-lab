import io

import pandas as pd
import pytest

from app.data_access.excel_profiler import profile_excel


class _Upload:
    """Minimal stand-in for a werkzeug FileStorage (same shape as test_excel_loader.py)."""

    def __init__(self, filename, stream):
        self.filename = filename
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _to_xlsx_bytes(rows):
    """rows: list of lists (no pandas header) -> raw .xlsx bytes."""
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    buf.seek(0)
    return buf


def _clean_xlsx_bytes():
    header = ["vendedor", "sede", "fecha", "neto"]
    rows = [header]
    for i in range(20):
        rows.append([f"V{i % 3}", f"S{i % 2}", 20260701 + i, 1000.0 + i])
    return _to_xlsx_bytes(rows)


def _matecol_like_xlsx_bytes(n_invoices=15):
    """Synthetic reproduction of the structure documented in
    GUIA_PRACTICA_FACTURAS_MATECOL.md sections 4 and 6 — invented data only,
    no real client names/NIT/amounts. Shape: 5 metadata rows, a header split
    across 2 rows, invoice rows interspersed with SUBTOTAL/blank rows, and
    trailing TOTALES rows.
    """
    rows = []
    # 5 metadata rows (sparse: only 1-2 filled cells out of 18)
    rows.append(["Hora:", "08:00", None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None])
    rows.append(["Fecha:", "2026-07-01", None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None])
    rows.append(["Usuario:", "demo", None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None])
    rows.append(["Periodo:", "202607", None, None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None, None])
    rows.append([None] * 18)

    # header split across 2 rows (first half of labels on one row, second half
    # on the next — reproduces the "encabezado partido en dos líneas" case)
    labels = ["cod_cliente", "nombre_cliente", "rep_legal", "factura", "dia",
              "vdor", "bod", "inv", "gravado", "excluido", "bruto",
              "descuento", "subtotal", "iva5", "iva19", "impoconsumo", "neto"]
    half = len(labels) // 2
    header_row_1 = [None] + labels[:half] + [None] * (18 - 1 - half)
    header_row_2 = [None] * (1 + half) + labels[half:] + [None] * (18 - 1 - half - len(labels[half:]))
    rows.append(header_row_1)
    rows.append(header_row_2)

    invoice_rows = []
    for i in range(n_invoices):
        invoice_rows.append([
            f"9000000{i}", f"CLIENTE INVENTADO {i}", "REPRESENTANTE X",
            f"F 0003{1000 + i}", 20260701 + i, str(i % 4), str(i % 2), "FE",
            100.0 + i, 0.0, 119.0 + i, 0.0, 100.0 + i, 5.0, 19.0 + i, 0.0,
            119.0 + i,
        ])
        if i % 5 == 4:
            invoice_rows.append(["SUBTOTAL TIPO --> " + str(i)] + [None] * 17)
        if i % 7 == 6:
            invoice_rows.append([None] * 18)
    rows.extend(invoice_rows)

    rows.append(["TOTALES -->"] + [None] * 17)
    rows.append(["TOT.DOCUMENTOS -->"] + [None] * 17)
    rows.append(["TOTALES ACUMULADO -->"] + [None] * 17)

    return _to_xlsx_bytes(rows), n_invoices


def test_clean_excel_is_usable_with_header_at_row_zero():
    result = profile_excel(_Upload("limpio.xlsx", _clean_xlsx_bytes()))
    assert result["verdict"] == "usable"
    assert result["header_row_index"] == 0
    types = {c["name"]: c["type"] for c in result["columns"]}
    assert types["vendedor"] == "categorica"
    assert types["neto"] == "numerica"
    assert types["fecha"] == "fecha"
    assert result["dataframe"] is not None
    assert list(result["dataframe"].columns) == ["vendedor", "sede", "fecha", "neto"]
    assert len(result["dataframe"]) == 20


def test_matecol_like_file_is_usable_con_limpieza():
    xlsx, n_invoices = _matecol_like_xlsx_bytes()
    result = profile_excel(_Upload("matecol.xlsx", xlsx))
    assert result["verdict"] == "usable_con_limpieza"
    assert result["header_row_index"] is not None
    assert result["header_row_index"] > 0
    assert result["columns"]
    assert result["detail"]
    assert result["dataframe"] is not None
    assert len(result["dataframe"]) == n_invoices


def test_empty_file_is_no_usable():
    empty = _to_xlsx_bytes([[None] * 5 for _ in range(5)])
    result = profile_excel(_Upload("vacio.xlsx", empty))
    assert result["verdict"] == "no_usable"
    assert result["header_row_index"] is None
    assert result["detail"]
    assert result["dataframe"] is None


def test_rejects_non_excel_extension():
    with pytest.raises(ValueError):
        profile_excel(_Upload("datos.csv", io.BytesIO(b"a,b\n1,2")))


def test_duplicate_header_labels_do_not_crash():
    """Real report headers sometimes reuse a label across split header cells
    (e.g. two columns both literally called "Cliente") — profiling must not
    blow up on that, it should dedupe the names."""
    header = ["cliente", "cliente", "neto", "cantidad"]
    rows = [header]
    for i in range(15):
        rows.append([f"C{i}", f"C{i} full name", 100.0 + i, i])
    xlsx = _to_xlsx_bytes(rows)

    result = profile_excel(_Upload("dup.xlsx", xlsx))

    assert result["verdict"] == "usable"
    names = [c["name"] for c in result["columns"]]
    assert names == ["cliente", "cliente_2", "neto", "cantidad"]


def test_numeric_column_keeps_numeric_dtype_not_object():
    """Regression: header=None reads used to leave every column as object
    dtype (the text header cell polluted the column before slicing), which
    silently broke df.describe()/select_dtypes for every bound upload."""
    import numpy as np

    result = profile_excel(_Upload("limpio.xlsx", _clean_xlsx_bytes()))
    df = result["dataframe"]
    assert pd.api.types.is_numeric_dtype(df["neto"])
    assert df.select_dtypes(include=[np.number]).columns.tolist() == ["neto"]
    assert df["neto"].mean() == pytest.approx(1009.5)


def test_no_real_header_is_no_usable_not_a_mangled_data_row():
    """A raw numeric dump with no header row at all must not have its first
    data row consumed as column names."""
    rows = [[100.0 + i, 200.0 + i, 300.0 + i] for i in range(20)]
    xlsx = _to_xlsx_bytes(rows)

    result = profile_excel(_Upload("sin_encabezado.xlsx", xlsx))

    assert result["verdict"] == "no_usable"
    assert result["header_row_index"] is None
    assert result["dataframe"] is None


def test_junk_pattern_matches_bare_tot_marker():
    from app.data_access.excel_profiler import JUNK_TEXT_PATTERN

    assert JUNK_TEXT_PATTERN.search("TOT.")
    assert JUNK_TEXT_PATTERN.search("TOT. ")
    assert JUNK_TEXT_PATTERN.search("TOT.DOCUMENTOS -->")
    assert not JUNK_TEXT_PATTERN.search("ROTOT.")


def test_profiling_a_representative_size_file_is_fast():
    import time

    xlsx, _ = _matecol_like_xlsx_bytes(n_invoices=300)
    start = time.perf_counter()
    result = profile_excel(_Upload("grande.xlsx", xlsx))
    elapsed = time.perf_counter() - start
    assert elapsed < 5
    assert result["verdict"] in ("usable", "usable_con_limpieza", "no_usable")
