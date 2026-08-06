import pandas as pd

from app.convatec.export import COMISION_ILUSTRATIVA_EXPORT_LABEL, preview_rows


def test_preview_rows_labels_comision_column_same_as_download():
    df = pd.DataFrame([{"Convenio": "X", "Comision_Ilustrativa": 50.0}])
    result = preview_rows(df, limit=10)
    assert COMISION_ILUSTRATIVA_EXPORT_LABEL in result["columns"]
    assert "Comision_Ilustrativa" not in result["columns"]
    assert result["rows"][0][COMISION_ILUSTRATIVA_EXPORT_LABEL] == 50.0


def test_preview_rows_converts_nan_and_timestamp_to_json_safe_values():
    df = pd.DataFrame(
        [{"Convenio": "X", "Representante": None, "Fecha Creación": pd.Timestamp("2026-07-01")}]
    )
    result = preview_rows(df, limit=10)
    row = result["rows"][0]
    assert row["Representante"] is None
    assert row["Fecha Creación"] == "2026-07-01 00:00:00"


def test_preview_rows_respects_limit_but_reports_total():
    df = pd.DataFrame([{"Convenio": f"C{i}"} for i in range(100)])
    result = preview_rows(df, limit=10)
    assert result["previewRows"] == 10
    assert result["totalRows"] == 100
    assert len(result["rows"]) == 10
