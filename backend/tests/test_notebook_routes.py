import io

import pandas as pd
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    return app.test_client()


def _clean_xlsx_bytes():
    buf = io.BytesIO()
    rows = [{"vendedor": f"V{i % 3}", "neto": 100.0 + i} for i in range(10)]
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def _high_cardinality_xlsx_bytes(n_rows=20):
    """A categorical column with more unique values than HIGH_CARDINALITY_THRESHOLD,
    like `No.Factura` in the real Matecol report referenced by Story 5.4's AC."""
    buf = io.BytesIO()
    rows = [{"factura": f"F{i:04d}", "neto": 100.0 + i} for i in range(n_rows)]
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def _messy_xlsx_bytes(n_rows=12):
    """One metadata row pushes the real header to row 1, so profile_excel()
    always returns verdict "usable_con_limpieza" for this fixture."""
    rows = [["Reporte generado:", None, None], ["vendedor", "neto", "cantidad"]]
    for i in range(n_rows):
        rows.append([f"V{i % 3}", 100.0 + i, i])
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    buf.seek(0)
    return buf


def test_upload_excel_response_includes_profile_without_breaking_existing_contract(client):
    data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}

    response = client.post("/api/notebook/upload-excel", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    result = body["data"]
    # existing contract, unchanged
    assert result["variable"] == "df"
    assert result["rows"] == 10
    assert result["columns"] == ["vendedor", "neto"]
    # new fields added by this story
    assert result["bound"] is True
    profile = result["profile"]
    assert profile["verdict"] == "usable"
    assert profile["headerRowIndex"] == 0
    assert {c["name"] for c in profile["columns"]} == {"vendedor", "neto"}


def test_upload_excel_still_rejects_non_excel_file(client):
    data = {"file": (io.BytesIO(b"a,b\n1,2"), "datos.csv")}

    response = client.post("/api/notebook/upload-excel", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False


def test_messy_excel_is_not_bound_until_confirmed(client):
    upload_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    upload_response = client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    upload_body = upload_response.get_json()
    assert upload_body["success"] is True
    result = upload_body["data"]
    assert result["bound"] is False
    assert result["profile"]["verdict"] == "usable_con_limpieza"
    assert result["profile"]["headerRowIndex"] == 1
    assert result["rows"] == 12
    assert set(result["columns"]) == {"vendedor", "neto", "cantidad"}

    # not bound yet: referencing the variable in a cell must fail
    exec_response = client.post("/api/notebook/execute", json={"code": "df.shape"})
    exec_body = exec_response.get_json()
    assert exec_body["data"]["error"] is not None
    assert exec_body["data"]["error"]["type"] == "NameError"

    confirm_response = client.post("/api/notebook/confirm-excel-cleanup")
    confirm_body = confirm_response.get_json()
    assert confirm_body["success"] is True
    confirmed = confirm_body["data"]
    assert confirmed["bound"] is True
    assert confirmed["variable"] == "df"
    assert confirmed["rows"] == 12
    # Regression: confirm-excel-cleanup must also return the column-type
    # profile, not just upload-excel's immediate-bind response - Epic 5's
    # "Gráfica sin código" panel reads this to populate its selectors, and
    # was otherwise unreachable for any Excel that needed cleanup.
    assert confirmed["profile"]["verdict"] == "usable_con_limpieza"
    assert {c["name"] for c in confirmed["profile"]["columns"]} == {"vendedor", "neto", "cantidad"}

    # now bound: the same session can use it
    exec_response_2 = client.post("/api/notebook/execute", json={"code": "df.shape[0]"})
    exec_body_2 = exec_response_2.get_json()
    assert exec_body_2["data"]["error"] is None
    assert exec_body_2["data"]["result_text"] == "12"


def test_confirm_excel_cleanup_without_pending_upload_is_rejected(client):
    response = client.post("/api/notebook/confirm-excel-cleanup")
    body = response.get_json()
    assert response.status_code == 400
    assert body["success"] is False


def test_cancel_excel_cleanup_discards_the_pending_upload(client):
    upload_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    cancel_response = client.post("/api/notebook/cancel-excel-cleanup")
    assert cancel_response.get_json()["success"] is True

    confirm_response = client.post("/api/notebook/confirm-excel-cleanup")
    assert confirm_response.status_code == 400


def test_uploading_a_clean_file_discards_a_previously_staged_pending_upload(client):
    """Regression: a stale "usable_con_limpieza" pending upload used to
    survive a later clean/broken upload for the same session, so a delayed
    confirm-excel-cleanup call could silently bind the discarded old file."""
    messy_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=messy_data, content_type="multipart/form-data")

    clean_data = {"file": (_clean_xlsx_bytes(), "limpio.xlsx")}
    clean_response = client.post("/api/notebook/upload-excel", data=clean_data, content_type="multipart/form-data")
    assert clean_response.get_json()["data"]["bound"] is True

    # the stale pending upload from the messy file must be gone, not silently bindable
    confirm_response = client.post("/api/notebook/confirm-excel-cleanup")
    assert confirm_response.status_code == 400


def test_confirm_excel_cleanup_restages_on_bind_timeout_instead_of_losing_data(client, monkeypatch):
    messy_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=messy_data, content_type="multipart/form-data")

    manager = client.application.config["WORKER_MANAGER"]
    original_bind = manager.bind
    calls = {"count": 0}

    def _flaky_bind(session_id, name, value):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("simulated timeout")
        return original_bind(session_id, name, value)

    monkeypatch.setattr(manager, "bind", _flaky_bind)

    first_response = client.post("/api/notebook/confirm-excel-cleanup")
    assert first_response.status_code == 504
    assert first_response.get_json()["success"] is False

    # the cleaned DataFrame must still be there to retry, not lost
    second_response = client.post("/api/notebook/confirm-excel-cleanup")
    second_body = second_response.get_json()
    assert second_body["success"] is True
    assert second_body["data"]["bound"] is True
    assert second_body["data"]["rows"] == 12


def test_generate_chart_returns_an_image_for_a_bound_dataframe(client):
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": "vendedor", "valueColumn": "neto", "chartType": "torta"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["error"] is None
    assert body["data"]["image_base64"]


def test_generate_chart_histograma_without_value_column_is_rejected(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": None, "valueColumn": None, "chartType": "histograma"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_generate_chart_rejects_unknown_chart_type(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": "vendedor", "valueColumn": None, "chartType": "scatter"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_generate_chart_for_missing_variable_surfaces_a_clean_error_not_500(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df_no_existe", "column": "vendedor", "valueColumn": None, "chartType": "barras"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["error"] is not None
    assert body["data"]["error"]["type"] == "NameError"


def test_generate_chart_cardinality_check_non_integer_result_is_a_clean_error(client, monkeypatch):
    """result_text is a display-string channel (execution.py's repr()), not a
    typed contract - if it's ever not a clean integer, the route must return
    a normal error response, not crash with an unhandled ValueError -> 500."""
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    manager = client.application.config["WORKER_MANAGER"]
    monkeypatch.setattr(
        manager,
        "execute",
        lambda session_id, code: {
            "stdout": "",
            "result_html": None,
            "result_text": "not-a-number",
            "image_base64": None,
            "error": None,
        },
    )

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": "vendedor", "valueColumn": "neto", "chartType": "torta"},
    )
    assert response.status_code == 502
    assert response.get_json()["success"] is False


def test_generate_chart_warns_on_high_cardinality_before_generating(client):
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": "factura", "valueColumn": "neto", "chartType": "torta"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    data = body["data"]
    assert data["needsConfirmation"] is True
    assert data["image_base64"] is None
    assert data["cardinalityWarning"]["column"] == "factura"
    assert data["cardinalityWarning"]["uniqueCount"] == 20
    assert data["cardinalityWarning"]["threshold"] == 15
    assert data["cardinalityWarning"]["suggestion"]


def test_generate_chart_with_force_generates_despite_high_cardinality(client):
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={
            "variable": "df",
            "column": "factura",
            "valueColumn": "neto",
            "chartType": "torta",
            "force": True,
        },
    )
    data = response.get_json()["data"]
    assert data["needsConfirmation"] is False
    assert data["cardinalityWarning"] is None
    assert data["error"] is None
    assert data["image_base64"]


def test_generate_chart_low_cardinality_never_warns(client):
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": "vendedor", "valueColumn": "neto", "chartType": "torta"},
    )
    data = response.get_json()["data"]
    assert data["needsConfirmation"] is False
    assert data["image_base64"]


def test_generate_chart_histograma_never_triggers_cardinality_warning(client):
    """histograma ignores the grouping column entirely (Story 5.2/5.3) - even
    with a high-cardinality column in the file, it must never warn. (The
    "linea never warns" half of this rule is covered at the unit level by
    test_chart_builder.py::test_needs_cardinality_check_only_for_torta_and_barras,
    since building a date-typed fixture here would need a real "fecha" column.)"""
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "column": None, "valueColumn": "neto", "chartType": "histograma"},
    )
    data = response.get_json()["data"]
    assert data["needsConfirmation"] is False
    assert data["image_base64"]


def test_no_usable_excel_is_not_bound_and_does_not_crash(client):
    empty = io.BytesIO()
    pd.DataFrame([[None] * 3 for _ in range(5)]).to_excel(empty, index=False, header=False)
    empty.seek(0)
    data = {"file": (empty, "vacio.xlsx")}

    response = client.post("/api/notebook/upload-excel", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    result = response.get_json()["data"]
    assert result["bound"] is False
    assert result["profile"]["verdict"] == "no_usable"
    assert result["rows"] == 0
    assert result["columns"] == []
