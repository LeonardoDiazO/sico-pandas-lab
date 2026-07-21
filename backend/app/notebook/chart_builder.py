"""Builds a Python code string for the no-code chart flow (Story 5.3).

The code is executed via the same WorkerManager.execute() path as any
notebook cell - CELL_TIMEOUT_SECONDS and figure capture come for free, no new
execution mechanism needed here.

Security note: `column`/`value_column`/`variable` come from user-uploaded
Excel content (Epic 4 profiling), not trusted source code - every value is
embedded via repr() (Python's own string-literal escaping), never through
manual string concatenation, so a stray quote in a column name can't break
or inject into the generated code.

Scope note (NFR10, Epic 6): chart_type/column/value_column are always one of
a small closed set already validated by the caller - this never builds code
from free-form user text.
"""

CHART_TYPES = {"torta", "barras", "linea", "histograma"}

# Pie/bar charts become unreadable well before 20 slices; a time series or a
# histogram bins/aggregates automatically so cardinality of the raw column
# isn't a legibility problem for those - the check only applies here.
HIGH_CARDINALITY_THRESHOLD = 15
_CARDINALITY_CHECK_TYPES = {"torta", "barras"}


def needs_cardinality_check(chart_type):
    return chart_type in _CARDINALITY_CHECK_TYPES


def build_cardinality_check_code(variable, column):
    """Lightweight `nunique()` probe, executed via the same WorkerManager as
    the real chart - the count comes back in the cell's result_text (see
    execution.py's _capture_value: repr(int) for a plain scalar).
    """
    return f"{variable}[{column!r}].nunique()"


def build_chart_code(chart_type, variable, column, value_column):
    """Returns a Python source string that, once executed, leaves a
    matplotlib figure ready to be captured as the cell result image.

    Raises ValueError for an unrecognized chart_type - callers must already
    validate against CHART_TYPES before calling this (closed-set selection).
    """
    if chart_type not in CHART_TYPES:
        raise ValueError(f"Tipo de gráfica no reconocido: {chart_type!r}")

    if chart_type in ("torta", "barras"):
        series_expr = _grouped_series_expr(variable, column, value_column)
        title = _title_for(column, value_column)
        plot_call = ".plot.pie(autopct='%1.1f%%', ylabel='')" if chart_type == "torta" else ".plot.bar()"
        return f"{series_expr}{plot_call}\nplt.title({title!r})\nplt.tight_layout()"

    if chart_type == "linea":
        dates_expr = f"pd.to_datetime({variable}[{column!r}], errors='coerce')"
        if value_column:
            series_expr = f"{variable}.groupby({dates_expr}.dt.date)[{value_column!r}].sum()"
            title = f"{value_column} por {column}"
        else:
            series_expr = f"{dates_expr}.value_counts().sort_index()"
            title = f"Cantidad de filas por {column}"
        return f"{series_expr}.plot.line()\nplt.title({title!r})\nplt.tight_layout()"

    # histograma: distribution of a single numeric column, grouping column ignored
    title = f"Distribución de {value_column}"
    return f"{variable}[{value_column!r}].plot.hist()\nplt.title({title!r})\nplt.tight_layout()"


def _grouped_series_expr(variable, column, value_column):
    if value_column:
        return f"{variable}.groupby({column!r})[{value_column!r}].sum().sort_values(ascending=False)"
    return f"{variable}[{column!r}].value_counts()"


def _title_for(column, value_column):
    if value_column:
        return f"{value_column} por {column}"
    return f"Cantidad de filas por {column}"
