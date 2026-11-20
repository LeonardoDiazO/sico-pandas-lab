"""Analysis corrections and learning connection (auditoría 2026-11-18):
money detection by word, aggregations, negatives/"(vacío)" out of the
ranking, Top N, trend, multi-sheet uploads, AI consent, daily AI ceiling and
anti-cheat guided challenges for every lesson."""
import datetime
import io
import json

import pandas as pd
import pytest

from app import create_app
from app.guided import content
from app.guided.challenges import CHALLENGES, run_checker
from app.notebook import routes as notebook_routes
from app.notebook.analysis_catalog import build_trend_code
from app.notebook.chart_builder import _looks_like_money
from app.notebook.execution import build_namespace, execute_code
from app.notebook.semantic_classifier import _llm_input_columns, classify_columns
from app.notebook.table_builder import build_column_values_code, build_summary_code
from app.notebook.worker_manager import WorkerManager


@pytest.fixture
def client():
    return create_app().test_client()


def _xlsx(frame):
    buf = io.BytesIO()
    frame.to_excel(buf, index=False)
    buf.seek(0)
    return buf


def _upload(client, buf, name="datos.xlsx"):
    return client.post(
        "/api/notebook/upload-excel", data={"file": (buf, name)}, content_type="multipart/form-data"
    ).get_json()


# --- money by word -----------------------------------------------------------


@pytest.mark.parametrize("name", ["Inventario", "Clientes activa", "Inventario final", "Actividad", "Saldoso", "Preciosidad"])
def test_money_is_not_detected_by_substring(name):
    assert _looks_like_money(name) is False


@pytest.mark.parametrize("name", ["Ventas", "Valor Neto", "ValorTotal", "valor_total", "I.V.A.", "Precios", "Saldo-Final"])
def test_money_is_detected_by_whole_word_plural_and_camel_case(name):
    assert _looks_like_money(name) is True


# --- table builder: negatives, vacío, top N, mean, filters ------------------


def _run(code, frame):
    ns = build_namespace()
    ns["df"] = frame
    return execute_code(code, ns)


def test_negative_net_groups_leave_the_ranking_and_are_listed_with_their_amount():
    frame = pd.DataFrame({"Cliente": ["A", "A", "B", "B", "C"], "Neto": [500, -100, 300, -300, -50]})
    result = _run(build_summary_code("df", ["Cliente"], "Neto"), frame)
    assert result["error"] is None
    clientes = [r["Cliente"] for r in result["result_records"]]
    assert clientes == ["A"]
    assert result["result_records"][-1]["% acumulado"] == 100.0
    lines = result["stdout"].splitlines()
    assert lines[0].startswith("1 de 1")  # 80/20 sentence first
    assert "Fuera del ranking: B = $ 0 (neto ≤ 0)" in lines
    assert "Fuera del ranking: C = $ -50 (neto ≤ 0)" in lines


def test_vacio_is_matched_exactly_not_by_substring():
    frame = pd.DataFrame({"V": ["A", None, "A"], "Z": ["x", "y", None], "Neto": [10, 20, 30]})
    result = _run(build_summary_code("df", ["V", "Z"], "Neto"), frame)
    keys = [r["index"] if "index" in r else list(r.values())[0] for r in result["result_records"]]
    # Composite keys containing "(vacío)" stay in the ranking.
    assert any("(vacío)" in str(k) for k in keys)
    assert "Fuera del ranking" not in (result["stdout"] or "")


def test_top_n_folds_the_tail_into_otros_without_changing_the_80_20_sentence():
    frame = pd.DataFrame({"Cliente": [f"C{i:02d}" for i in range(88)], "Neto": list(range(88, 0, -1))})
    result = _run(build_summary_code("df", ["Cliente"], "Neto", top_n=15), frame)
    assert result["error"] is None
    records = result["result_records"]
    assert len(records) == 16
    assert records[-1]["Cliente"] == "Otros (73)"
    assert records[-1]["% acumulado"] == 100.0
    assert "de 88 categorías" in result["stdout"]


def test_mean_aggregation_ranks_groups_by_their_average():
    frame = pd.DataFrame({"V": ["A", "A", "B"], "Precio": [10.0, 30.0, 25.0]})
    result = _run(build_summary_code("df", ["V"], "Precio", agg="mean"), frame)
    assert [r["V"] for r in result["result_records"]] == ["B", "A"]
    assert result["result_records"][0]["Precio"] == "$ 25"


def test_filter_on_numeric_column_with_blanks_matches_the_label_the_dashboard_shows():
    frame = pd.DataFrame({"Vdor": [3, 3, None, 4], "Neto": [10, 20, 30, 40]})
    values = _run(build_column_values_code("df", "Vdor"), frame)["result_records"]
    assert [v["Vdor"] for v in values] == ["3", "4"]
    filtered = _run(build_summary_code("df", ["Vdor"], "Neto", filters=[{"column": "Vdor", "values": ["3"]}]), frame)
    assert filtered["error"] is None
    assert len(filtered["result_records"]) == 1
    assert filtered["result_records"][0]["Neto"] == "$ 30"


# --- trend ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "fechas",
    [
        [46027.5, 46042.25, 46083.0, 46111.9],  # Excel serials, fractional
        [20260105, 20260120, 20260302, 20260330],  # YYYYMMDD numbers
        ["2026-01-05", "2026-01-20", "2026-03-02", "2026-03-30"],
    ],
)
def test_trend_handles_serials_numbers_and_text_and_fills_empty_months(fechas):
    frame = pd.DataFrame({"F": fechas, "Neto": [100, 200, 300, 50]})
    result = _run(build_trend_code("df", "F", "Neto"), frame)
    assert result["error"] is None, result["error"]
    meses = [r["Mes"] for r in result["result_records"]]
    assert meses == ["2026-01", "2026-02", "2026-03"]
    assert result["result_records"][1]["Neto"] == "$ 0"


# --- routes: summary agg, auto-analysis, sheets --------------------------------


def test_summary_table_accepts_valid_agg_and_rejects_invalid(client):
    _upload(client, _xlsx(pd.DataFrame({"V": ["A", "A", "B"], "Precio": [10.0, 30.0, 25.0]})))
    ok = client.post(
        "/api/notebook/summary-table", json={"variable": "df", "columns": ["V"], "valueColumn": "Precio", "agg": "mean"}
    ).get_json()
    assert ok["success"] is True
    assert [r["V"] for r in ok["data"]["result_records"]] == ["B", "A"]
    bad = client.post(
        "/api/notebook/summary-table", json={"variable": "df", "columns": ["V"], "valueColumn": "Precio", "agg": "max"}
    )
    assert bad.status_code == 400


def test_auto_analysis_returns_code_that_reproduces_the_table_and_supports_filters(client):
    frame = pd.DataFrame(
        {"Vendedor": ["Ana", "Luis", "Ana", "Marta"] * 5, "Ciudad": ["Cali", "Bogota"] * 10, "Neto": range(1, 21)}
    )
    _upload(client, _xlsx(frame))
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Ciudad", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]
    body = client.post("/api/notebook/auto-analysis", json={"classifications": classifications}).get_json()
    block = body["data"]["bloques"][0]
    rerun = client.post("/api/notebook/execute", json={"code": block["codigo"]}).get_json()["data"]
    assert rerun["result_records"] == block["resultado"]["result_records"]

    filtered = client.post(
        "/api/notebook/auto-analysis",
        json={"classifications": classifications, "filters": [{"column": "Ciudad", "values": ["Cali"]}]},
    ).get_json()
    assert filtered["data"]["resumen"]["filtros"] == [{"column": "Ciudad", "values": ["Cali"]}]
    ciudad_blocks = [b for b in filtered["data"]["bloques"] if b["dimension"] == "Ciudad"]
    # Cardinality computed over the filtered rows: Ciudad has 1 value left.
    assert ciudad_blocks == []
    assert {"dimension": "Ciudad", "valores": 1} in filtered["data"]["resumen"]["omitidas"]

    bad = client.post(
        "/api/notebook/auto-analysis",
        json={"classifications": classifications, "filters": [{"column": "NoExiste", "values": ["x"]}]},
    )
    assert bad.status_code == 400


def _three_sheet_book():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as writer:
        pd.DataFrame({"Vendedor": ["A", "B"], "Neto": [10.0, 20.0]}).to_excel(writer, sheet_name="Ene", index=False)
        pd.DataFrame({"Vendedor": ["C"], "Neto": [5.0], "Extra": [1]}).to_excel(writer, sheet_name="Feb", index=False)
        pd.DataFrame({"Vendedor": ["D", "E", "F"], "Neto": [1.0, 2.0, 3.0]}).to_excel(writer, sheet_name="Mar", index=False)
    buf.seek(0)
    return buf


def test_multi_sheet_upload_asks_for_selection_then_stacks_with_hoja(client):
    body = _upload(client, _three_sheet_book())
    assert body["data"]["needsSheetSelection"] is True
    assert body["data"]["bound"] is False
    assert [s["name"] for s in body["data"]["sheets"]] == ["Ene", "Feb", "Mar"]

    chosen = client.post("/api/notebook/select-sheets", json={"sheets": ["Ene", "Mar"]}).get_json()
    assert chosen["success"] is True and chosen["data"]["bound"] is True
    assert chosen["data"]["rows"] == 5
    assert chosen["data"]["columns"][0] == "Hoja"
    assert chosen["data"]["profile"]["headerRowIndex"] is None
    assert chosen["data"]["warning"] is None
    check = client.post("/api/notebook/execute", json={"code": "df['Hoja'].value_counts().to_dict()"}).get_json()
    assert check["data"]["result_text"] == "{'Mar': 3, 'Ene': 2}"


def test_select_sheets_with_different_columns_warns_and_keeps_common_ones(client):
    _upload(client, _three_sheet_book())
    body = client.post("/api/notebook/select-sheets", json={"sheets": ["Ene", "Feb"]}).get_json()
    assert body["data"]["columns"] == ["Hoja", "Vendedor", "Neto"]
    assert "Extra (hoja Feb)" in body["data"]["warning"]
    # The workbook is kept: the user can drop the odd sheet and re-select.
    again = client.post("/api/notebook/select-sheets", json={"sheets": ["Ene"]}).get_json()
    assert again["success"] is True and again["data"]["rows"] == 2


def test_select_sheets_rejects_unknown_and_dedupes(client):
    _upload(client, _three_sheet_book())
    assert client.post("/api/notebook/select-sheets", json={"sheets": ["Abr"]}).status_code == 400
    assert client.post("/api/notebook/select-sheets", json={"sheets": []}).status_code == 400
    body = client.post("/api/notebook/select-sheets", json={"sheets": ["Ene", "Ene"]}).get_json()
    assert body["data"]["sheetsUsed"] == ["Ene"]
    assert "Hoja" not in body["data"]["columns"]  # a single sheet is not stacked


def test_single_sheet_upload_skips_the_selection_step(client):
    body = _upload(client, _xlsx(pd.DataFrame({"V": ["A", "B"], "Neto": [1.0, 2.0]})))
    assert body["data"]["needsSheetSelection"] is False
    assert body["data"]["bound"] is True


# --- AI: consent, payload, daily ceiling --------------------------------------


_NARRATIVE_PAYLOAD = {
    "valueColumnRow": "Neto",
    "rowStats": {"total": 10, "cruce_80": 2, "pct_base": 20},
    "rowRecords": [{"Neto": 5}],
    "groupColumnsLabel": "Vendedor",
    "valueColumnGroup": "Neto",
    "groupStats": {"total": 10, "cruce_80": 1, "pct_base": 50},
    "groupRecords": [{"Vendedor": "A", "Neto": 5}],
}


def test_pareto_narrative_requires_explicit_consent(client):
    response = client.post("/api/notebook/pareto-narrative", json=_NARRATIVE_PAYLOAD)
    assert response.status_code == 400
    assert "Confirma" in response.get_json()["message"]


def test_pareto_narrative_with_consent_calls_the_assistant(client, monkeypatch):
    sent = {}

    def _fake(stats):
        sent["stats"] = stats
        return "Texto generado."

    monkeypatch.setattr(notebook_routes, "generate_pareto_narrative", _fake)
    response = client.post("/api/notebook/pareto-narrative", json={**_NARRATIVE_PAYLOAD, "consent": True})
    assert response.status_code == 200
    assert response.get_json()["data"]["narrative"] == "Texto generado."
    assert sent["stats"]["grupos"] == _NARRATIVE_PAYLOAD["groupRecords"]


def test_classifier_sends_only_names_and_types():
    columns = [{"name": "Vendedor", "type": "categorica", "uniqueRatio": 0.1, "sampleValues": ["Ana Secreta"]}]
    assert _llm_input_columns(columns) == [{"name": "Vendedor", "type": "categorica"}]

    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            captured["contents"] = contents

            class _R:
                text = json.dumps({"classifications": [{"name": "Vendedor", "role": "dimension"}]})

            return _R()

    class _Client:
        models = _Models()

    classify_columns(columns, client=_Client())
    assert "Ana Secreta" not in captured["contents"]
    assert "uniqueRatio" not in captured["contents"]


def test_global_daily_assistant_ceiling_applies_across_sessions_and_resets_next_day():
    day = {"value": datetime.date(2026, 11, 18)}
    manager = WorkerManager(assistant_max_requests=10, assistant_max_requests_per_day=2, today=lambda: day["value"])
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s2") is True
    assert manager.check_and_increment_assistant_usage("s3") is False  # global ceiling
    manager.release_assistant_usage("s2")
    assert manager.check_and_increment_assistant_usage("s3") is True
    day["value"] = datetime.date(2026, 11, 19)
    assert manager.check_and_increment_assistant_usage("s4") is True


# --- guided: every lesson has a challenge, reference solutions pass -----------


REFERENCE_SOLUTIONS = {
    "00-python-desde-cero": "precio = 25000\ncantidad = 4\ntotal_compra = precio * cantidad",
    "01-fundamentos": "total_cantidad = df_02_movimiento['mov_cantidad'].sum()",
    "02-filtrar-ordenar": (
        "top_movimientos = df_02_movimiento[df_02_movimiento['mov_cantidad'] > 0]"
        ".sort_values('mov_neto', ascending=False)"
    ),
    "03-agrupar": "resultado = df_02_movimiento.groupby('mov_item')['mov_neto'].sum().sort_values(ascending=False)",
    "04-combinar-tablas": (
        "con_descripcion = pd.merge(df_02_movimiento, df_02_item, left_on='mov_item', "
        "right_on='item_codigo', how='left')"
    ),
    "05-graficas": "serie_grafica = df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum()\nserie_grafica.plot(kind='bar')",
    "06-limpieza": "clientes_limpios = df_clientes.drop_duplicates().dropna(subset=['ciudad'])",
    "07-fechas": (
        "fechas = pd.to_datetime(df_ventas['fecha'])\n"
        "ventas_por_mes = df_ventas.groupby(fechas.dt.to_period('M'))['neto'].sum()"
    ),
    "08-razonamiento": (
        "netos = df_ventas.groupby('cliente')['neto'].sum()\n"
        "ranking = netos[netos > 0].sort_values(ascending=False)"
    ),
}


def test_every_lesson_00_to_08_has_a_challenge():
    ids = [lesson["id"] for lesson in content.LESSONS]
    assert ids[0].startswith("00-") and ids[-1].startswith("08-") and len(ids) == 9
    for lesson in content.LESSONS:
        assert lesson.get("challenge_id") in CHALLENGES, lesson["id"]


@pytest.mark.parametrize("lesson", content.LESSONS, ids=lambda l: l["id"])
def test_steps_alone_do_not_pass_but_the_reference_solution_does(lesson):
    ns = build_namespace()
    for step in lesson["steps"]:
        result = execute_code(step["code"], ns)
        assert result["error"] is None, (lesson["id"], step["title"], result["error"])
    challenge_id = lesson["challenge_id"]
    assert run_checker(challenge_id, ns)["passed"] is False

    solution = execute_code(REFERENCE_SOLUTIONS[lesson["id"]], ns)
    assert solution["error"] is None, solution["error"]
    verdict = run_checker(challenge_id, ns, had_chart=bool(solution["chart_svg"]))
    assert verdict["passed"] is True, (lesson["id"], verdict["message"])


def test_lesson_08_example_has_a_client_with_non_positive_net():
    ns = build_namespace()
    lesson = next(l for l in content.LESSONS if l["id"] == "08-razonamiento")
    execute_code(lesson["steps"][0]["code"], ns)
    netos = ns["df_ventas"].groupby("cliente")["neto"].sum()
    assert (netos <= 0).any()


def _check(client, challenge_id, code):
    return client.post("/api/guided/challenge/check", json={"code": code, "challenge_id": challenge_id}).get_json()[
        "data"
    ]


def test_cheating_by_replacing_the_table_does_not_pass(client):
    step = content.LESSONS[1]["steps"][1]["code"]  # 1.2 creates df_02_movimiento
    client.post("/api/notebook/execute", json={"code": step})
    data = _check(
        client,
        "01-fundamentos:reto-1",
        "df_02_movimiento = df_02_movimiento.head(1)\ntotal_cantidad = df_02_movimiento['mov_cantidad'].sum()",
    )
    assert data["challenge"]["passed"] is False
    assert "compara contra los datos originales" in data["challenge"]["message"]


def test_synthetic_table_typed_by_the_learner_before_the_step_is_not_the_reference(client):
    data = _check(
        client,
        "01-fundamentos:reto-1",
        "df_02_movimiento = pd.DataFrame({'mov_item': ['X'], 'mov_cantidad': [999]})\n"
        "total_cantidad = df_02_movimiento['mov_cantidad'].sum()",
    )
    assert data["challenge"]["passed"] is False


def test_bound_upload_is_compared_against_its_untouched_copy(client):
    _upload(client, _xlsx(pd.DataFrame({"Vendedor": ["A", "B", "A"], "Cantidad": [1, 2, 3], "Neto": [5.0, 6.0, 7.0]})))
    cheat = _check(client, "01-fundamentos:reto-1", "df = df.head(1)\ntotal_cantidad = df['Cantidad'].sum()")
    assert cheat["challenge"]["passed"] is False


def test_graficas_challenge_needs_a_chart_end_to_end(client):
    step = content.LESSONS[5]["steps"][0]["code"]
    client.post("/api/notebook/execute", json={"code": step})
    no_chart = _check(client, "05-graficas:reto-1", "serie_grafica = df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum()")
    assert no_chart["challenge"]["passed"] is False
    assert "gráfica" in no_chart["challenge"]["message"]
    with_chart = _check(
        client,
        "05-graficas:reto-1",
        "serie_grafica = df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum()\nserie_grafica.plot(kind='bar')",
    )
    assert with_chart["challenge"]["passed"] is True


# --- Review pass 2 (2026-11-19) -------------------------------------------


def test_trend_reads_yyyymm_and_year_numbers_and_day_one_months_are_complete():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.analysis_catalog import build_trend_code
    from app.notebook.execution import build_namespace, execute_code

    ns = build_namespace()
    ns["df"] = pd.DataFrame({"periodo": [202601, 202602, 202603], "neto": [10.0, 20.0, 30.0]})
    result = execute_code(build_trend_code("df", "periodo", "neto"), ns)
    assert result["error"] is None
    assert [r["Mes"] for r in result["result_records"]] == ["2026-01", "2026-02", "2026-03"]
    assert "incomplet" not in (result["stdout"] or "").lower()

    ns = build_namespace()
    ns["df"] = pd.DataFrame({"fecha": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]), "neto": [1.0, 2.0, 3.0]})
    result = execute_code(build_trend_code("df", "fecha", "neto"), ns)
    assert result["error"] is None
    assert "incomplet" not in (result["stdout"] or "").lower()


def test_book_with_unusable_first_sheet_binds_the_usable_one(client):
    import io

    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame({"Portada": ["Informe de ventas"]}).to_excel(writer, sheet_name="Portada", index=False, header=False)
        pd.DataFrame({"cliente": ["A", "B", "C"], "neto": [1.0, 2.0, 3.0]}).to_excel(writer, sheet_name="Datos", index=False)
    buf.seek(0)
    res = client.post(
        "/api/notebook/upload-excel",
        data={"file": (buf, "libro.xlsx"), "variable": "df"},
        content_type="multipart/form-data",
    )
    data = res.get_json()["data"]
    assert data["needsSheetSelection"] is False
    assert data["sheetsUsed"] == ["Datos"]
    assert data["rows"] == 3


def test_quality_counts_removed_totals_and_empty_rows_separately():
    import pandas as pd

    from app.data_access.excel_profiler import profile_raw

    raw = pd.DataFrame(
        [
            ["vendedor", "neto"],
            ["A", 10.0],
            ["B", 20.0],
            [None, None],
            ["C", 30.0],
            ["TOTAL GENERAL", 60.0],
        ]
    )
    profile = profile_raw(raw)
    quality = profile["quality"]
    assert quality["totalsRowsRemoved"] == 1
    assert quality["emptyRowsRemoved"] == 1


def test_money_words_glued_to_punctuation_or_digits():
    from app.notebook.chart_builder import _looks_like_money

    for name in ("Valor($)", "Neto:", "Venta2026"):
        assert _looks_like_money(name), name
    assert not _looks_like_money("Inventario2026")
