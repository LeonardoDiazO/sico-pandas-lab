"""Pure execution logic for a single notebook cell.

Kept free of any multiprocessing / Flask concerns so it can be unit tested
directly. The worker process (worker.py) calls execute_code() inside an
isolated child process; nothing here talks to the network or the database.
"""
import ast
import base64
import io
import traceback
from contextlib import redirect_stdout

# Hard caps so a single cell cannot flood the response with megabytes of text.
MAX_STDOUT_CHARS = 20000
MAX_RESULT_ROWS = 200


def build_namespace():
    """Fresh namespace pre-seeded with the libraries a data-analysis learner expects.

    pd/np/plt/sns/stats are already imported so the user never has to guess
    what to import — the guided module explains what each one is for.
    """
    import matplotlib

    matplotlib.use("Agg")  # headless backend, no display needed
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import seaborn as sns
    from scipy import stats

    sns.set_theme(style="whitegrid")

    return {
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "stats": stats,
        "__builtins__": __builtins__,
    }


def _truncate(text, limit):
    if text is None:
        return None
    if len(text) > limit:
        return text[:limit] + f"\n... (salida truncada, {len(text) - limit} caracteres más)"
    return text


def _capture_value(value):
    """Render the value of a cell's last expression, Jupyter-style."""
    if value is None:
        return None, None
    try:
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            html = value.head(MAX_RESULT_ROWS).to_html(
                classes="dataframe", border=0, max_cols=50
            )
            note = ""
            if len(value) > MAX_RESULT_ROWS:
                note = (
                    f"<p class='df-note'>Mostrando {MAX_RESULT_ROWS} de "
                    f"{len(value)} filas.</p>"
                )
            return html + note, None
        if isinstance(value, pd.Series):
            return value.head(MAX_RESULT_ROWS).to_frame().to_html(
                classes="dataframe", border=0
            ), None
    except Exception:
        pass
    return None, _truncate(repr(value), MAX_STDOUT_CHARS)


def _capture_figure(namespace):
    """Grab the most recent matplotlib figure as a base64 PNG, if any."""
    plt = namespace.get("plt")
    if plt is None:
        return None
    fignums = plt.get_fignums()
    if not fignums:
        return None
    fig = plt.figure(fignums[-1])
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=90)
    finally:
        plt.close("all")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def execute_code(code, namespace):
    """Execute one cell against a persistent namespace.

    Returns a plain dict (JSON-serialisable) describing the outcome. Never
    raises for user code errors — those are captured into the ``error`` field
    so the session survives and the frontend can show a clear message.
    """
    stdout_buffer = io.StringIO()
    result_html = None
    result_text = None
    image_base64 = None
    error = None

    try:
        parsed = ast.parse(code)
    except SyntaxError as exc:
        return {
            "stdout": "",
            "result_html": None,
            "result_text": None,
            "image_base64": None,
            "error": {
                "type": "SyntaxError",
                "message": str(exc.msg),
                "traceback": traceback.format_exc(limit=1),
            },
        }

    last_expr = None
    if parsed.body and isinstance(parsed.body[-1], ast.Expr):
        last_expr = parsed.body.pop()

    try:
        module = ast.Module(body=parsed.body, type_ignores=[])
        compiled = compile(module, "<celda>", "exec")
        with redirect_stdout(stdout_buffer):
            exec(compiled, namespace)
            if last_expr is not None:
                value = eval(
                    compile(ast.Expression(last_expr.value), "<celda>", "eval"),
                    namespace,
                )
                result_html, result_text = _capture_value(value)
        image_base64 = _capture_figure(namespace)
    except Exception as exc:  # noqa: BLE001 - user code, must not escape
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }

    return {
        "stdout": _truncate(stdout_buffer.getvalue(), MAX_STDOUT_CHARS),
        "result_html": result_html,
        "result_text": result_text,
        "image_base64": image_base64,
        "error": error,
    }
