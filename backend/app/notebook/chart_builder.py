"""Builds a Python code string for the no-code chart flow (Story 5.3;
multi-column grouping added in Story 7.2).

The code is executed via the same WorkerManager.execute() path as any
notebook cell - CELL_TIMEOUT_SECONDS and figure capture come for free, no new
execution mechanism needed here.

Security note: `columns`/`value_column`/`variable` come from user-uploaded
Excel content (Epic 4 profiling), not trusted source code - every value is
embedded via repr() (Python's own string-literal escaping), never through
manual string concatenation, so a stray quote in a column name can't break
or inject into the generated code. repr() of a list of strings produces a
valid, safe Python list literal (e.g. ['vendedor', 'mes']) - the same
guarantee extends naturally from single strings to lists.

Scope note (NFR10, Epic 6): chart_type/columns/value_column are always one of
a small closed set already validated by the caller - this never builds code
from free-form user text.
"""

CHART_TYPES = {"torta", "barras", "linea", "histograma"}

# Pie/bar charts become unreadable well before 20 slices; a time series or a
# histogram bins/aggregates automatically so cardinality of the raw column
# isn't a legibility problem for those - the check only applies here.
HIGH_CARDINALITY_THRESHOLD = 15
_CARDINALITY_CHECK_TYPES = {"torta", "barras"}

# Distinct from HIGH_CARDINALITY_THRESHOLD above: that one decides when to
# WARN before generating at all (Story 5.4). This one decides how many
# individual slices a torta actually draws once generation proceeds (Story
# 7.4) - a pie chart is unreadable well before 15 slices, so the rest get
# folded into a single "Otros" slice instead of rendering dozens of slivers.
TOP_N_SLICES_FOR_TORTA = 8


def needs_cardinality_check(chart_type):
    return chart_type in _CARDINALITY_CHECK_TYPES


def build_cardinality_check_code(variable, columns):
    """Lightweight cardinality probe, executed via the same WorkerManager as
    the real chart - the count comes back in the cell's result_text (see
    execution.py's _capture_value: repr(int) for a plain scalar).

    One column: `nunique()` (unchanged from pre-7.2 - Story 7.2 AC3). Several
    columns: the number of unique combinations across all of them (Story
    7.2 AC6) - a composite key can have far more distinct values than any
    single column in it.
    """
    if len(columns) == 1:
        return f"{variable}[{columns[0]!r}].nunique()"
    return f"{variable}[{columns!r}].drop_duplicates().shape[0]"


def build_chart_code(chart_type, variable, columns, value_column):
    """Returns a Python source string that, once executed, leaves a
    matplotlib figure ready to be captured as the cell result image.

    `columns` is a list of column names (never None; empty for chart types
    that ignore it, e.g. histograma). `linea` always takes exactly one
    column - callers must enforce that before calling this (see
    routes.py::generate_chart, Story 7.2 AC4).

    Raises ValueError for an unrecognized chart_type - callers must already
    validate against CHART_TYPES before calling this (closed-set selection).
    """
    if chart_type not in CHART_TYPES:
        raise ValueError(f"Tipo de gráfica no reconocido: {chart_type!r}")

    if chart_type in ("torta", "barras"):
        series_expr = _grouped_series_expr(variable, columns, value_column)
        title = _title_for(columns, value_column)
        if chart_type == "torta":
            series_expr = _limit_to_top_n_plus_others(series_expr, TOP_N_SLICES_FOR_TORTA)
            # Epic 7 code review: two runtime-only failure modes pd.concat()
            # alone doesn't cover (chart_builder.py never sees real data, so
            # these must live in the generated expression, same reasoning as
            # _limit_to_top_n_plus_others itself). groupby(level=0).sum()
            # folds a real category that happens to be named "Otros" together
            # with the synthetic bucket (pd.concat would otherwise leave two
            # same-labeled wedges); clip(lower=0) prevents a negative tail sum
            # (e.g. a signed "neto" column with more refunds than sales in the
            # tail) from raising matplotlib's "pie plot doesn't allow negative
            # values" - a pie chart has no meaningful way to show a negative
            # slice, so it's floored to zero instead of crashing.
            series_expr = f"{series_expr}.groupby(level=0, sort=False).sum().clip(lower=0)"
            plot_call = ".plot.pie(autopct='%1.1f%%', ylabel='', figsize=(8, 8))"
        else:
            plot_call = ".plot.bar()"
        return f"{series_expr}{plot_call}\nplt.title({title!r})\nplt.tight_layout()"

    if chart_type == "linea":
        column = columns[0]
        dates_expr = f"pd.to_datetime({variable}[{column!r}], errors='coerce')"
        if value_column:
            series_expr = f"{variable}.groupby({dates_expr}.dt.date)[{value_column!r}].sum()"
            title = f"{value_column} por {column}"
        else:
            series_expr = f"{dates_expr}.value_counts().sort_index()"
            title = f"Cantidad de filas por {column}"
        return f"{series_expr}.plot.line()\nplt.title({title!r})\nplt.tight_layout()"

    # histograma: distribution of a single numeric column, grouping columns ignored
    title = f"Distribución de {value_column}"
    return f"{variable}[{value_column!r}].plot.hist()\nplt.title({title!r})\nplt.tight_layout()"


def _grouping_expr(variable, columns):
    """What to group by: the column name directly when there's one
    (identical to the pre-7.2 code - never touch this branch), or a
    "composite key" joined as a string when there's more than one - avoids
    matplotlib rendering raw Python-tuple labels (e.g. "('V0', 'Enero')")
    on the chart's axis/legend.
    """
    if len(columns) == 1:
        return f"{variable}[{columns[0]!r}]"
    # fillna() before astype(str) - otherwise a null cell in one of several
    # grouping columns renders as the literal substring "nan" in the
    # composite label (e.g. "V0 - nan"), which reads as a data-quality bug
    # rather than a real "missing" placeholder (Epic 7 code review).
    return f"{variable}[{columns!r}].fillna('(vacío)').astype(str).agg(' - '.join, axis=1)"


def _grouped_series_expr(variable, columns, value_column):
    if value_column:
        if len(columns) == 1:
            return f"{variable}.groupby({columns[0]!r})[{value_column!r}].sum().sort_values(ascending=False)"
        return (
            f"{variable}.groupby({_grouping_expr(variable, columns)})"
            f"[{value_column!r}].sum().sort_values(ascending=False)"
        )
    if len(columns) == 1:
        return f"{variable}[{columns[0]!r}].value_counts()"
    return f"{_grouping_expr(variable, columns)}.value_counts()"


def _limit_to_top_n_plus_others(series_expr, top_n):
    """If the series (already sorted descending by _grouped_series_expr) has
    more than top_n entries, keep the top_n by value and fold the rest into
    a single 'Otros' slice - keeps a pie chart's slice count legible instead
    of rendering dozens of near-invisible slivers (Story 7.4)."""
    return (
        f"(lambda _s: _s if len(_s) <= {top_n} else "
        f"pd.concat([_s.iloc[:{top_n}], pd.Series({{'Otros': _s.iloc[{top_n}:].sum()}})]))"
        f"({series_expr})"
    )


def _title_for(columns, value_column):
    label = columns[0] if len(columns) == 1 else ", ".join(columns)
    if value_column:
        return f"{value_column} por {label}"
    return f"Cantidad de filas por {label}"
