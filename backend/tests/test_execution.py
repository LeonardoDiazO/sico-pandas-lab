from app.notebook.execution import build_namespace, execute_code


def run(code, ns=None):
    ns = ns if ns is not None else build_namespace()
    return execute_code(code, ns), ns


def test_stdout_is_captured():
    result, _ = run("print('hola')")
    assert result["error"] is None
    assert "hola" in result["stdout"]


def test_last_expression_dataframe_renders_html():
    result, _ = run("import pandas as pd\npd.DataFrame({'a':[1,2]})")
    assert result["error"] is None
    assert result["result_html"] is not None
    assert "table" in result["result_html"]


def test_namespace_persists_across_cells():
    ns = build_namespace()
    execute_code("x = 41", ns)
    result = execute_code("x + 1", ns)
    assert result["result_text"] == "42"


def test_runtime_error_is_captured_not_raised():
    result, _ = run("1 / 0")
    assert result["error"] is not None
    assert result["error"]["type"] == "ZeroDivisionError"


def test_syntax_error_is_captured():
    result, _ = run("def broken(:")
    assert result["error"] is not None
    assert result["error"]["type"] == "SyntaxError"


def test_error_does_not_wipe_prior_state():
    ns = build_namespace()
    execute_code("y = 10", ns)
    execute_code("boom", ns)  # NameError
    result = execute_code("y", ns)
    assert result["result_text"] == "10"


def test_matplotlib_figure_is_captured_as_base64():
    result, _ = run(
        "import matplotlib.pyplot as plt\nplt.plot([1,2,3],[4,5,6])"
    )
    assert result["error"] is None
    assert result["image_base64"] is not None
    assert len(result["image_base64"]) > 100


def test_dataframe_result_also_includes_json_records():
    """result_records lets a frontend build a non-table view (e.g. KPI
    cards) from the same rows the HTML table already shows, without
    re-parsing HTML."""
    result, _ = run("import pandas as pd\npd.DataFrame({'a': [1, 2], 'b': ['x', 'y']})")
    assert result["error"] is None
    assert result["result_records"] == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_dataframe_result_records_replace_nan_with_none():
    result, _ = run("import pandas as pd\nimport numpy as np\npd.DataFrame({'a': [1, np.nan]})")
    assert result["error"] is None
    assert result["result_records"] == [{"a": 1.0}, {"a": None}]


def test_non_dataframe_result_has_no_records():
    result, _ = run("1 + 1")
    assert result["error"] is None
    assert result["result_records"] is None


def test_grouped_summary_index_becomes_a_named_column_in_records():
    """table_builder.py's build_summary_code() returns a DataFrame indexed
    by the group name (e.g. groupby('Tipo Costo').sum()'s own index) - the
    HTML table already shows that via to_html()'s automatic index column,
    but to_json(orient='records') silently drops the index unless folded
    into a real column first. Without that fold, a KPI-card view built from
    result_records would have the totals/percentages but no group name to
    label them with."""
    code = (
        "import pandas as pd\n"
        "s = pd.Series({'MATERIALES': 900.0, 'OBRA': 100.0})\n"
        "s.index.name = 'Tipo Costo'\n"
        "s.to_frame('valor')"
    )
    result, _ = run(code)
    assert result["error"] is None
    assert result["result_records"] == [
        {"Tipo Costo": "MATERIALES", "valor": 900.0},
        {"Tipo Costo": "OBRA", "valor": 100.0},
    ]
