import io

import openpyxl
import pytest

from app.convatec.comision_externa_referencia import ComisionExternaError, load_comision_externa


class _Upload:
    def __init__(self, filename, stream):
        self.filename = filename
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _build_workbook(rows, include_subtotal=True):
    """Mimics the real file: a header row at (0-indexed) row 6, detail
    rows, then optional SUBTOTAL/TOTALES rows that must be excluded."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja2"
    headers = ["Vendedor", "Tipo", "No.Factura", "Dia", "Bod", "Gravado", "Exento", "Bruto", "I.V.A.", "Flete", "N E T O", "Com", "Comision"]
    for i, h in enumerate(headers):
        ws.cell(row=7, column=1 + i, value=h)  # Excel row 7 = 0-indexed row 6
    r = 8
    for row in rows:
        ws.cell(row=r, column=1, value=row["vendedor"])
        ws.cell(row=r, column=11, value=row["neto"])
        ws.cell(row=r, column=12, value=row["porcentaje"])
        ws.cell(row=r, column=13, value=row["comision"])
        r += 1
    if include_subtotal:
        ws.cell(row=r, column=1, value="SUBTOTAL VENDEDOR --> 00")
        ws.cell(row=r, column=11, value=sum(row["neto"] for row in rows))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return _Upload("comision.xls", buf)


def test_aggregates_neto_and_comision_per_vendedor():
    upload = _build_workbook(
        [
            {"vendedor": "VEGA BELEÑO CARLOS", "neto": 100.0, "porcentaje": 20.0, "comision": 20.0},
            {"vendedor": "VEGA BELEÑO CARLOS", "neto": 200.0, "porcentaje": 20.0, "comision": 40.0},
        ]
    )
    result = load_comision_externa(upload)
    assert result == [{"vendedor": "VEGA BELEÑO CARLOS", "neto": 300.0, "porcentaje": 20.0, "comision": 60.0}]


def test_excludes_subtotal_and_totales_rows():
    upload = _build_workbook([{"vendedor": "X", "neto": 50.0, "porcentaje": 10.0, "comision": 5.0}])
    result = load_comision_externa(upload)
    assert len(result) == 1
    assert result[0]["vendedor"] == "X"


def test_missing_required_columns_raises_user_facing_error():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hoja2"
    ws.cell(row=7, column=1, value="Vendedor")
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    with pytest.raises(ComisionExternaError, match="N E T O"):
        load_comision_externa(_Upload("comision.xls", buf))


def test_rejects_non_excel_extension():
    buf = io.BytesIO(b"not an excel file")
    with pytest.raises(ComisionExternaError, match="Excel"):
        load_comision_externa(_Upload("comision.csv", buf))
