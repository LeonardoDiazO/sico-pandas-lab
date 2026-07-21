import io

import pandas as pd
import pytest

from app.data_access.excel_loader import load_excel_dataframe, read_excel_raw


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


def test_load_excel_dataframe_and_read_excel_raw_can_both_read_same_upload():
    """Both functions must seek(0) internally so the same FileStorage can be
    profiled and then loaded without the caller managing stream position."""
    upload = _Upload("datos.xlsx", _xlsx_bytes())
    raw = read_excel_raw(upload)
    df = load_excel_dataframe(upload)
    assert raw.shape == (3, 2)
    assert list(df.columns) == ["a", "b"]
