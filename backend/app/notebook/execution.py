"""Pure execution logic for a single notebook cell.

Kept free of any multiprocessing / Flask concerns so it can be unit tested
directly. The worker process (worker.py) calls execute_code() inside an
isolated child process; nothing here talks to the network or the database.
"""
import ast
import html
import io
import json
import re
import traceback
import urllib.parse
from contextlib import redirect_stdout

# Hard caps so a single cell cannot flood the response with megabytes of text.
MAX_STDOUT_CHARS = 20000
MAX_RESULT_ROWS = 200


CELL_FILENAME = "<celda>"

# Top-level modules a cell may import. Everything a learner needs for data
# analysis, nothing that reaches the OS, the network or other processes.
ALLOWED_IMPORTS = frozenset(
    {
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "scipy",
        "math",
        "statistics",
        "datetime",
        "re",
        "json",
        "collections",
        "itertools",
        # Only its `parse` submodule - see _guarded_import.
        "urllib",
    }
)

# Removed from the builtins a cell sees: file access, dynamic code execution
# and interactive prompts. The backend's own code keeps the real builtins.
BLOCKED_BUILTINS = frozenset({"open", "exec", "eval", "compile", "input", "breakpoint"})

IMPORT_BLOCKED_MESSAGE = "El import de '{name}' no está permitido en este entorno."
IO_BLOCKED_MESSAGE = "Leer o escribir archivos no está permitido en este entorno."


def _import_blocked(name):
    return ImportError(IMPORT_BLOCKED_MESSAGE.format(name=name))


def _make_guarded_import(real_import):
    """__import__ replacement for the builtins a cell sees.

    Only imports whose calling frame is a cell (`<celda>`) are filtered, so
    pandas/matplotlib keep importing `os`, `urllib.request`, etc. internally.
    `urllib` is special: `import urllib.parse` would normally bind the whole
    `urllib` package - which already carries `urllib.request` because pandas
    imported it - so a cell only ever gets an object exposing `parse`.
    """
    import dis
    import sys
    import types
    import urllib.parse as _urllib_parse

    parse_only = types.SimpleNamespace(parse=_urllib_parse)
    import_name_op = dis.opmap["IMPORT_NAME"]

    def _is_import_statement(frame):
        """True when the cell frame is executing an `import` statement right
        now. C code running on behalf of a cell (e.g. `strftime` lazily
        importing `time`) also resolves __import__ through the cell's
        builtins, with the cell as the nearest Python frame - those internal
        imports must keep working."""
        try:
            return frame.f_code.co_code[frame.f_lasti] == import_name_op
        except (IndexError, AttributeError):
            return True

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        caller = sys._getframe(1)
        if caller.f_code.co_filename != CELL_FILENAME:
            return real_import(name, globals, locals, fromlist, level)
        if not _is_import_statement(caller):
            # Not an `import` statement but called from a cell: C code running
            # on its behalf (allowed) or a direct `__builtins__['__import__']`
            # call - never hand out the OS / process / network modules here.
            if name.split(".")[0] in DIRECT_CALL_DENIED:
                raise _import_blocked(name)
            return real_import(name, globals, locals, fromlist, level)
        if level != 0:
            raise _import_blocked(name)
        top = name.split(".")[0]
        if top not in ALLOWED_IMPORTS:
            raise _import_blocked(name)
        if top == "urllib":
            if name == "urllib.parse" and fromlist:
                return _urllib_parse
            if name == "urllib.parse" or (name == "urllib" and fromlist and set(fromlist) <= {"parse"}):
                return parse_only
            raise _import_blocked(name)
        return real_import(name, globals, locals, fromlist, level)

    return _guarded_import


def build_safe_builtins():
    """A COPY of the builtins with a filtered __import__ and without the
    names in BLOCKED_BUILTINS - the real `builtins` module is never mutated
    (the backend itself still needs open/exec/compile).

    Threat model: this stops accidents and casual abuse (`import os`,
    `open('/etc/passwd')`), not a determined attacker - Python's object model
    has known escapes (e.g. `pd.__builtins__`). See worker.py.
    """
    import builtins

    safe = {k: v for k, v in vars(builtins).items() if k not in BLOCKED_BUILTINS}
    safe["__import__"] = _make_guarded_import(builtins.__import__)
    return safe


def _blocked_direct_import(name, *args, **kwargs):
    """Shadows `__import__` as a NAME in the cell namespace: `import x`
    statements use the builtins' (guarded) __import__, while a direct call
    `__import__('os')` resolves this global first."""
    raise _import_blocked(name)


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
        "__builtins__": build_safe_builtins(),
        "__import__": _blocked_direct_import,
    }


# --- File / URL / pickle I/O through the analysis libraries -----------------
#
# Blocking `open` and `import os` is not enough: pandas, numpy and matplotlib
# read and write paths and URLs on their own (`pd.read_csv('/proc/self/
# environ')`, `df.to_csv('/tmp/x')`, `pd.read_pickle(...)` which can execute
# code). install_io_guards() wraps those entry points IN THE WORKER PROCESS
# ONLY: a str/bytes/PathLike target raises PermissionError, in-memory buffers
# (StringIO/BytesIO) keep working - _capture_figure() itself saves to a
# StringIO. pickle readers/writers are blocked outright. The backend never
# needs file I/O inside the worker: data arrives through `bind`.

# Modules a cell may never obtain through a direct __import__ call (see
# _guarded_import): the OS, processes, the filesystem and the network.
DIRECT_CALL_DENIED = frozenset(
    {
        "os", "posix", "nt", "sys", "subprocess", "socket", "ssl", "shutil", "pathlib",
        "importlib", "ctypes", "multiprocessing", "threading", "_thread", "signal", "pty",
        "builtins", "io", "_io", "http", "ftplib", "smtplib", "telnetlib", "requests",
        "pickle", "marshal", "shelve", "tempfile", "glob", "fileinput", "code", "codeop",
        "runpy", "inspect", "gc", "resource",
    }
)

_PATH_KWARGS = (
    "filepath_or_buffer",
    "path_or_buf",
    "path_or_buffer",
    "path",
    "io",
    "buf",
    "excel_writer",
    "fname",
    "file",
    "frame",
)

_PANDAS_READERS = (
    "read_csv", "read_table", "read_fwf", "read_excel", "read_json", "read_html",
    "read_xml", "read_parquet", "read_feather", "read_orc", "read_sas", "read_spss",
    "read_stata", "read_hdf",
)
_PANDAS_ALWAYS_BLOCKED = ("read_pickle", "to_pickle", "read_clipboard")
_PANDAS_WRITERS = (
    "to_csv", "to_excel", "to_json", "to_html", "to_xml", "to_parquet", "to_feather",
    "to_orc", "to_stata", "to_hdf", "to_markdown", "to_latex", "to_string",
)
_PANDAS_WRITERS_ALWAYS_BLOCKED = ("to_pickle", "to_clipboard", "to_sql")
_NUMPY_FUNCS = ("load", "save", "savez", "savez_compressed", "fromfile", "loadtxt", "genfromtxt", "savetxt")


def _is_path_target(target):
    import os

    return isinstance(target, (str, bytes, os.PathLike))


def _io_target(args, kwargs, position):
    if len(args) > position:
        return args[position]
    for key in _PATH_KWARGS:
        if key in kwargs:
            return kwargs[key]
    return None


def _guard(func, position, always=False):
    import functools

    if getattr(func, "__sico_io_guard__", False):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if always or _is_path_target(_io_target(args, kwargs, position)):
            raise PermissionError(IO_BLOCKED_MESSAGE)
        return func(*args, **kwargs)

    wrapper.__sico_io_guard__ = True
    return wrapper


def install_io_guards():
    """Wrap the path-based I/O entry points of pandas, numpy and matplotlib.
    Idempotent. Must only run inside a worker process - it patches the
    libraries process-wide."""
    import matplotlib.figure
    import numpy as np
    import pandas as pd

    for name in _PANDAS_READERS:
        if hasattr(pd, name):
            setattr(pd, name, _guard(getattr(pd, name), 0))
    for name in _PANDAS_ALWAYS_BLOCKED:
        if hasattr(pd, name):
            setattr(pd, name, _guard(getattr(pd, name), 0, always=True))
    for cls in (pd.DataFrame, pd.Series):
        for name in _PANDAS_WRITERS:
            if hasattr(cls, name):
                setattr(cls, name, _guard(getattr(cls, name), 1))
        for name in _PANDAS_WRITERS_ALWAYS_BLOCKED:
            if hasattr(cls, name):
                setattr(cls, name, _guard(getattr(cls, name), 1, always=True))
    for name in _NUMPY_FUNCS:
        if hasattr(np, name):
            setattr(np, name, _guard(getattr(np, name), 0))
    # plt.savefig() delegates to Figure.savefig, so one patch covers both.
    matplotlib.figure.Figure.savefig = _guard(matplotlib.figure.Figure.savefig, 1)

    # Aliases reachable by module path (pd.io.parsers.read_csv, pd.ExcelFile,
    # ...) all open files through pandas.io.common.get_handle - guard it in
    # every already-imported pandas module that holds a reference, and in
    # pandas.io.common itself for modules imported later.
    import sys as _sys

    import pandas.io.common as pd_common

    guarded_handle = _guard(pd_common.get_handle, 0)
    for mod_name, mod in list(_sys.modules.items()):
        if mod_name.startswith("pandas") and getattr(mod, "get_handle", None) is not None:
            try:
                mod.get_handle = guarded_handle
            except (AttributeError, TypeError):
                pass
    for name in ("ExcelFile", "ExcelWriter", "HDFStore"):
        if hasattr(pd, name):
            setattr(pd, name, _guard(getattr(pd, name), 0))

    import numpy.lib.npyio as npyio

    for name in _NUMPY_FUNCS:
        if hasattr(npyio, name):
            setattr(npyio, name, _guard(getattr(npyio, name), 0))
    np.memmap = _guard(np.memmap, 0)
    if hasattr(np, "DataSource"):
        np.DataSource = _guard(np.DataSource, 0, always=True)
    if hasattr(np.lib, "npyio") and hasattr(np.lib.npyio, "DataSource"):
        np.lib.npyio.DataSource = _guard(np.lib.npyio.DataSource, 0, always=True)

    import matplotlib.image as mpl_image

    mpl_image.imread = _guard(mpl_image.imread, 0)
    mpl_image.imsave = _guard(mpl_image.imsave, 0)

    try:
        import scipy.io as scipy_io
        import scipy.io.wavfile as wavfile

        for name in ("loadmat", "savemat", "mmread", "mmwrite", "readsav", "whosmat"):
            if hasattr(scipy_io, name):
                setattr(scipy_io, name, _guard(getattr(scipy_io, name), 0))
        wavfile.read = _guard(wavfile.read, 0)
        wavfile.write = _guard(wavfile.write, 0)
    except ImportError:
        pass

    try:
        import seaborn as sns

        # Downloads from the internet - no network from a cell.
        sns.load_dataset = _guard(sns.load_dataset, 0, always=True)
    except ImportError:
        pass


def _truncate(text, limit):
    if text is None:
        return None
    if len(text) > limit:
        return text[:limit] + f"\n... (salida truncada, {len(text) - limit} caracteres más)"
    return text


def _capture_value(value):
    """Render the value of a cell's last expression, Jupyter-style.

    Returns (result_html, result_text, result_records). result_records is a
    JSON-safe list of row dicts (same MAX_RESULT_ROWS cap as the HTML table,
    same rows) - purely additive alongside the HTML table, which stays the
    primary rendering every existing consumer (app-cell-result) already
    uses. It exists so a frontend component can build a non-table view (e.g.
    KPI cards) from the exact same data without re-parsing HTML - only
    populated for a DataFrame, since that's the only shape callers need it
    for today (table_builder.py's summary/sort code).
    """
    if value is None:
        return None, None, None
    try:
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            head = value.head(MAX_RESULT_ROWS)
            html = head.to_html(classes="dataframe", border=0, max_cols=50)
            note = ""
            if len(value) > MAX_RESULT_ROWS:
                note = (
                    f"<p class='df-note'>Mostrando {MAX_RESULT_ROWS} de "
                    f"{len(value)} filas.</p>"
                )
            # A non-default index (e.g. table_builder.py's grouped summary,
            # indexed by the group name) carries real information the HTML
            # table already shows via to_html()'s own index column - fold it
            # into a real column here too, otherwise to_json(orient="records")
            # would silently drop it (unlike to_html(), it never includes the
            # index). A fresh RangeIndex (the common case - a plain df.head())
            # carries no information, so it's left alone rather than adding a
            # noisy, meaningless "index" key to every record.
            records_source = head if isinstance(head.index, pd.RangeIndex) else head.reset_index()
            # to_json() (not a manual dict comprehension) so NaN/NaT/Timestamp
            # values get the same safe, standard handling pandas already
            # gives the HTML table above, instead of a second bespoke
            # serialization that could diverge from it.
            records = json.loads(records_source.to_json(orient="records", date_format="iso"))
            return html + note, None, records
        if isinstance(value, pd.Series):
            return (
                value.head(MAX_RESULT_ROWS).to_frame().to_html(classes="dataframe", border=0),
                None,
                None,
            )
    except Exception:
        pass
    return None, _truncate(repr(value), MAX_STDOUT_CHARS), None


# User feedback: "sería bueno tener un tooltip... para diferenciar[los]
# cuando no caben todos los representantes" - chart_builder.py/table_builder.py
# hide x-axis labels past a cardinality threshold (otherwise dozens of
# overlapping labels are worse than none), so hovering is the only way left
# to find out which bar/wedge is which. Any artist a chart-building module
# wants hoverable gets `artist.set_gid("tt-" + urllib.parse.quote(label))`
# BEFORE the figure is saved - _SVG_TOOLTIP_PATTERN below finds every SVG
# group with that gid and injects a <title> as its first child. <title> is
# the standard, native SVG/HTML way to attach a hover tooltip - the browser
# shows it with zero JavaScript, but ONLY when the SVG is inline in the DOM
# (not referenced via <img src=...>, which is why _capture_figure below
# returns raw SVG markup instead of a base64 PNG - see notebook-home's
# app-cell-result, which renders it via [innerHTML] like the table already
# is). URL-encoding the label (not raw text) before it goes into the gid
# guarantees the id attribute only ever contains URL-safe characters,
# sidestepping any question of how completely matplotlib's own SVG writer
# escapes arbitrary text in an id="..." attribute.
_SVG_TOOLTIP_PATTERN = re.compile(r'(<g id="tt-([^"]*)"[^>]*>)')


def _inject_svg_tooltips(svg_text):
    def _replace(match):
        opening_tag, encoded_label = match.group(1), match.group(2)
        label = urllib.parse.unquote(encoded_label)
        return f"{opening_tag}<title>{html.escape(label)}</title>"

    return _SVG_TOOLTIP_PATTERN.sub(_replace, svg_text)


def _capture_figure(namespace):
    """Grab the most recent matplotlib figure as inline SVG markup (not a
    base64 PNG - see _inject_svg_tooltips' docstring for why native <title>
    hover tooltips need that)."""
    plt = namespace.get("plt")
    if plt is None:
        return None
    fignums = plt.get_fignums()
    if not fignums:
        return None
    fig = plt.figure(fignums[-1])
    buf = io.StringIO()
    try:
        fig.savefig(buf, format="svg", bbox_inches="tight")
    finally:
        plt.close("all")
    return _inject_svg_tooltips(buf.getvalue())


def execute_code(code, namespace):
    """Execute one cell against a persistent namespace.

    Returns a plain dict (JSON-serialisable) describing the outcome. Never
    raises for user code errors — those are captured into the ``error`` field
    so the session survives and the frontend can show a clear message.
    """
    stdout_buffer = io.StringIO()
    result_html = None
    result_text = None
    result_records = None
    chart_svg = None
    error = None

    try:
        parsed = ast.parse(code)
    except SyntaxError as exc:
        return {
            "stdout": "",
            "result_html": None,
            "result_text": None,
            "result_records": None,
            "chart_svg": None,
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
        compiled = compile(module, CELL_FILENAME, "exec")
        with redirect_stdout(stdout_buffer):
            exec(compiled, namespace)
            if last_expr is not None:
                value = eval(
                    compile(ast.Expression(last_expr.value), CELL_FILENAME, "eval"),
                    namespace,
                )
                result_html, result_text, result_records = _capture_value(value)
        chart_svg = _capture_figure(namespace)
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
        "result_records": result_records,
        "chart_svg": chart_svg,
        "error": error,
    }
