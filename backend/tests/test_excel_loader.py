import io

import pandas as pd
import pytest

from app.data_access.excel_loader import _detect_engine, load_excel_dataframe, read_excel_raw


class _Upload:
    """Minimal stand-in for a werkzeug FileStorage.

    Delegates every file method (read/seek/tell/...) to the wrapped stream so
    pandas/openpyxl treats it like a real file object.
    """

    def __init__(self, filename, stream):
        self.filename = filename
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _xlsx_bytes():
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_reads_valid_xlsx():
    df = load_excel_dataframe(_Upload("datos.xlsx", _xlsx_bytes()))
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (2, 2)


def test_rejects_non_excel_extension():
    with pytest.raises(ValueError):
        load_excel_dataframe(_Upload("datos.csv", io.BytesIO(b"a,b\n1,2")))


def test_rejects_corrupt_excel():
    with pytest.raises(ValueError):
        load_excel_dataframe(_Upload("roto.xlsx", io.BytesIO(b"no soy un excel")))


def test_read_excel_raw_has_no_header_row():
    df = read_excel_raw(_Upload("datos.xlsx", _xlsx_bytes()))
    # header=None: the original header ("a", "b") is row 0 of the data, not consumed as column names
    assert list(df.columns) == [0, 1]
    assert df.shape == (3, 2)
    assert list(df.iloc[0]) == ["a", "b"]


def test_read_excel_raw_rejects_non_excel_extension():
    with pytest.raises(ValueError):
        read_excel_raw(_Upload("datos.csv", io.BytesIO(b"a,b\n1,2")))


def test_read_excel_raw_rejects_corrupt_excel():
    with pytest.raises(ValueError):
        read_excel_raw(_Upload("roto.xlsx", io.BytesIO(b"no soy un excel")))


def test_xls_extension_with_real_xlsx_content_still_reads_correctly():
    """Regression: a real production file (est_proveedorvdart_admon.xls) is
    a modern XLSX/OOXML file some ERP exported with a ".xls" extension -
    forcing engine="openpyxl" happened to work for this exact shape, but
    only because openpyxl was hardcoded; the point of _detect_engine is that
    it works by looking at the actual content, not by accident of which
    engine happened to be hardcoded."""
    df = load_excel_dataframe(_Upload("reporte.xls", _xlsx_bytes()))
    assert list(df.columns) == ["a", "b"]


def test_detect_engine_picks_xlrd_for_ole2_signature():
    """Regression: a genuine legacy Excel 97-2003 (.xls) file is an OLE2/BIFF
    binary, NOT a zip - forcing engine="openpyxl" (OOXML-only) on one raised
    a confusing "BadZipFile: File is not a zip file" even though xlrd (which
    reads exactly this format) was already a project dependency, just never
    wired in. Detecting by the file's own signature (not the extension, which
    the test above shows can't be trusted either way) picks the engine that
    can actually read it."""
    ole2_like = io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
    assert _detect_engine(ole2_like) == "xlrd"
    # Must rewind after peeking at the signature, so the actual read below
    # starts from byte 0 like every other caller expects.
    assert ole2_like.tell() == 0


def test_detect_engine_picks_openpyxl_for_zip_signature():
    assert _detect_engine(_xlsx_bytes()) == "openpyxl"


def test_load_excel_dataframe_and_read_excel_raw_can_both_read_same_upload():
    """Both functions must seek(0) internally so the same FileStorage can be
    profiled and then loaded without the caller managing stream position."""
    upload = _Upload("datos.xlsx", _xlsx_bytes())
    raw = read_excel_raw(upload)
    df = load_excel_dataframe(upload)
    assert raw.shape == (3, 2)
    assert list(df.columns) == ["a", "b"]
