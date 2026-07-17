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
