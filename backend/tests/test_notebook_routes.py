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


def test_confirm_excel_cleanup_excludes_selected_columns(client):
    """New: the user can deselect columns they don't need on the cleanup
    preview screen before confirming - those columns must not end up in the
    bound DataFrame nor in the returned profile."""
    messy_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=messy_data, content_type="multipart/form-data")

    confirm_response = client.post(
        "/api/notebook/confirm-excel-cleanup", json={"excludeColumns": ["cantidad"]}
    )
    confirm_body = confirm_response.get_json()
    assert confirm_response.status_code == 200
    assert confirm_body["success"] is True
    confirmed = confirm_body["data"]
    assert set(confirmed["columns"]) == {"vendedor", "neto"}
    assert {c["name"] for c in confirmed["profile"]["columns"]} == {"vendedor", "neto"}

    exec_response = client.post("/api/notebook/execute", json={"code": "list(df.columns)"})
    exec_body = exec_response.get_json()
    assert exec_body["data"]["error"] is None
    assert "cantidad" not in exec_body["data"]["result_text"]


def test_confirm_excel_cleanup_ignores_unknown_exclude_column_names(client):
    messy_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=messy_data, content_type="multipart/form-data")

    confirm_response = client.post(
        "/api/notebook/confirm-excel-cleanup", json={"excludeColumns": ["no_existe"]}
    )
    confirm_body = confirm_response.get_json()
    assert confirm_response.status_code == 200
    assert set(confirm_body["data"]["columns"]) == {"vendedor", "neto", "cantidad"}


def test_confirm_excel_cleanup_rejects_excluding_all_columns(client):
    messy_data = {"file": (_messy_xlsx_bytes(), "sucio.xlsx")}
    client.post("/api/notebook/upload-excel", data=messy_data, content_type="multipart/form-data")

    confirm_response = client.post(
        "/api/notebook/confirm-excel-cleanup",
        json={"excludeColumns": ["vendedor", "neto", "cantidad"]},
    )
    assert confirm_response.status_code == 400
    assert confirm_response.get_json()["success"] is False

    # the pending upload must still be there to retry with a valid selection
    retry_response = client.post("/api/notebook/confirm-excel-cleanup", json={"excludeColumns": []})
    assert retry_response.get_json()["success"] is True


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
        json={"variable": "df", "columns": ["vendedor"], "valueColumn": "neto", "chartType": "torta"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["error"] is None
    assert body["data"]["image_base64"]


def test_generate_chart_histograma_without_value_column_is_rejected(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": [], "valueColumn": None, "chartType": "histograma"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_generate_chart_rejects_unknown_chart_type(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": ["vendedor"], "valueColumn": None, "chartType": "scatter"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_generate_chart_for_missing_variable_surfaces_a_clean_error_not_500(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df_no_existe", "columns": ["vendedor"], "valueColumn": None, "chartType": "barras"},
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
        json={"variable": "df", "columns": ["vendedor"], "valueColumn": "neto", "chartType": "torta"},
    )
    assert response.status_code == 502
    assert response.get_json()["success"] is False


def test_generate_chart_warns_on_high_cardinality_before_generating(client):
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": ["factura"], "valueColumn": "neto", "chartType": "torta"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    data = body["data"]
    assert data["needsConfirmation"] is True
    assert data["image_base64"] is None
    assert data["cardinalityWarning"]["columns"] == ["factura"]
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
            "columns": ["factura"],
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
        json={"variable": "df", "columns": ["vendedor"], "valueColumn": "neto", "chartType": "torta"},
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
        json={"variable": "df", "columns": [], "valueColumn": "neto", "chartType": "histograma"},
    )
    data = response.get_json()["data"]
    assert data["needsConfirmation"] is False
    assert data["image_base64"]


def test_generate_chart_histograma_without_columns_key_succeeds(client):
    """Regression test (Epic 7 code review) - histograma never uses grouping
    columns (Story 5.2/5.3), so a caller that omits the `columns` field
    entirely (the pre-Story-7.2 shape for this chart type) must still
    succeed, not get a blanket 400 from the new list-shape validation."""
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "valueColumn": "neto", "chartType": "histograma"},
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["error"] is None
    assert body["data"]["image_base64"]


# --- Story 7.2: multiple columns -----------------------------------------------


def _two_categorical_columns_xlsx_bytes():
    """Unlike _clean_xlsx_bytes() (only "vendedor"/"neto" - kept minimal so
    other tests asserting its exact column list don't break), this fixture
    has two categorical columns to group by together. Includes a second
    numeric column ("cantidad") so at least half the row is numeric -
    mostly-categorical rows can otherwise fool _detect_header_row()'s
    data-vs-header walk (a pre-existing excel_profiler.py characteristic,
    unrelated to this story - not something to fix here, just avoid tripping
    it with an unnecessarily text-heavy fixture)."""
    buf = io.BytesIO()
    rows = [
        {"vendedor": f"V{i % 3}", "sede": f"S{i % 2}", "cantidad": i + 1, "neto": 100.0 + i}
        for i in range(10)
    ]
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_generate_chart_with_multiple_categorical_columns_succeeds(client):
    upload_data = {"file": (_two_categorical_columns_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={
            "variable": "df",
            "columns": ["vendedor", "sede"],
            "valueColumn": "neto",
            "chartType": "barras",
        },
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["error"] is None
    assert body["data"]["image_base64"]


def test_generate_chart_linea_rejects_multiple_columns(client):
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={
            "variable": "df",
            "columns": ["vendedor", "sede"],
            "valueColumn": "neto",
            "chartType": "linea",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_generate_chart_cardinality_check_uses_combined_columns(client):
    """Variant of test_generate_chart_warns_on_high_cardinality_before_generating
    (Story 5.4) - with 2+ columns, the cardinality check must run over the
    combination, not just the first column, so it can warn even when no
    single selected column alone is high-cardinality."""
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": ["factura", "neto"], "valueColumn": None, "chartType": "barras"},
    )
    body = response.get_json()
    data = body["data"]
    assert data["needsConfirmation"] is True
    assert data["cardinalityWarning"]["columns"] == ["factura", "neto"]
    assert data["cardinalityWarning"]["uniqueCount"] >= 20


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


# --- POST /api/notebook/interpret-chart-request (Story 6.1) -----------------------

_COLUMNS_PAYLOAD = [
    {"name": "vendedor", "type": "categorica"},
    {"name": "neto", "type": "numerica"},
]


def test_interpret_chart_request_resolved_returns_200_with_selection(client, monkeypatch):
    monkeypatch.setattr(
        "app.notebook.routes.interpret_chart_request",
        lambda question, columns: {
            "resolved": True,
            "column": "vendedor",
            "valueColumn": None,
            "chartType": "torta",
            "reason": None,
        },
    )
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"] == {
        "resolved": True,
        "column": "vendedor",
        "valueColumn": None,
        "chartType": "torta",
        "reason": None,
    }


def test_interpret_chart_request_unresolved_is_still_a_200_not_an_error(client, monkeypatch):
    """Same discriminant pattern as cardinalityWarning (Story 5.4) - "couldn't
    resolve this" is a valid feature outcome, not an HTTP error."""
    monkeypatch.setattr(
        "app.notebook.routes.interpret_chart_request",
        lambda question, columns: {
            "resolved": False,
            "column": None,
            "valueColumn": None,
            "chartType": None,
            "reason": "No puedo comparar dos periodos con una sola gráfica.",
        },
    )
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "compárame julio contra junio", "columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["resolved"] is False
    assert "comparar" in body["data"]["reason"]


def test_interpret_chart_request_missing_question_is_400(client):
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_interpret_chart_request_blank_question_is_400(client):
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "   ", "columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_interpret_chart_request_missing_columns_is_400(client):
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_interpret_chart_request_empty_columns_is_400(client):
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": []},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_interpret_chart_request_malformed_columns_is_400(client):
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": ["vendedor"]},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_interpret_chart_request_unavailable_interpreter_is_503_not_500(client, monkeypatch):
    from app.notebook.nl_chart_interpreter import InterpreterUnavailableError

    def _raise(question, columns):
        raise InterpreterUnavailableError("El asistente no está disponible en este momento.")

    monkeypatch.setattr("app.notebook.routes.interpret_chart_request", _raise)
    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 503
    body = response.get_json()
    assert body["success"] is False
    assert "no está disponible" in body["message"]


# --- Story 6.2: per-session rate limit on the assistant -----------------------------


def _stub_resolved_interpretation(question, columns):
    return {
        "resolved": True,
        "column": "vendedor",
        "valueColumn": None,
        "chartType": "torta",
        "reason": None,
    }


def test_interpret_chart_request_limit_reached_returns_429_and_never_calls_interpreter(client, monkeypatch):
    manager = client.application.config["WORKER_MANAGER"]
    manager.assistant_max_requests = 0

    def _fail_if_called(question, columns):
        raise AssertionError("interpret_chart_request must not be called once the session limit is reached")

    monkeypatch.setattr("app.notebook.routes.interpret_chart_request", _fail_if_called)

    response = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
    )
    assert response.status_code == 429
    body = response.get_json()
    assert body["success"] is False
    assert "límite" in body["message"].lower()


def test_interpret_chart_request_sessions_have_independent_limits(client, monkeypatch):
    manager = client.application.config["WORKER_MANAGER"]
    manager.assistant_max_requests = 1
    monkeypatch.setattr("app.notebook.routes.interpret_chart_request", _stub_resolved_interpretation)

    first = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
        headers={"X-Session-Id": "session-a"},
    )
    assert first.status_code == 200

    exhausted = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "otra pregunta", "columns": _COLUMNS_PAYLOAD},
        headers={"X-Session-Id": "session-a"},
    )
    assert exhausted.status_code == 429

    other_session = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
        headers={"X-Session-Id": "session-b"},
    )
    assert other_session.status_code == 200


# --- Story 7.3: plain-language chart explanation ----------------------------------


def test_generate_chart_response_includes_explanation_on_success(client):
    upload_data = {"file": (_clean_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": ["vendedor"], "valueColumn": "neto", "chartType": "torta"},
    )
    data = response.get_json()["data"]
    assert data["explanation"]
    assert "vendedor" in data["explanation"]
    assert "neto" in data["explanation"]


def test_generate_chart_explanation_is_null_when_cardinality_warning_blocks_generation(client):
    upload_data = {"file": (_high_cardinality_xlsx_bytes(), "datos.xlsx")}
    client.post("/api/notebook/upload-excel", data=upload_data, content_type="multipart/form-data")

    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df", "columns": ["factura"], "valueColumn": "neto", "chartType": "torta"},
    )
    data = response.get_json()["data"]
    assert data["needsConfirmation"] is True
    assert data["explanation"] is None


def test_generate_chart_explanation_is_null_on_execution_error(client):
    response = client.post(
        "/api/notebook/generate-chart",
        json={"variable": "df_no_existe", "columns": ["vendedor"], "valueColumn": None, "chartType": "barras"},
    )
    data = response.get_json()["data"]
    assert data["error"] is not None
    assert data["explanation"] is None


def test_interpret_chart_request_unavailable_does_not_permanently_consume_quota(client, monkeypatch):
    """Regression test (Epic 6 code review): a provider outage / missing API
    key must not burn through the session's limited assistant budget with
    zero successful answers - the reserved slot is refunded on
    InterpreterUnavailableError."""
    from app.notebook.nl_chart_interpreter import InterpreterUnavailableError

    manager = client.application.config["WORKER_MANAGER"]
    manager.assistant_max_requests = 1

    def _raise(question, columns):
        raise InterpreterUnavailableError("El asistente no está disponible en este momento.")

    monkeypatch.setattr("app.notebook.routes.interpret_chart_request", _raise)

    headers = {"X-Session-Id": "refund-test-session"}
    first = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "hazme una torta por vendedor", "columns": _COLUMNS_PAYLOAD},
        headers=headers,
    )
    assert first.status_code == 503

    second = client.post(
        "/api/notebook/interpret-chart-request",
        json={"question": "otra pregunta", "columns": _COLUMNS_PAYLOAD},
        headers=headers,
    )
    # still 503 (interpreter still unavailable), NOT 429 - the failed first
    # attempt must not have consumed the session's only allowed slot
    assert second.status_code == 503
