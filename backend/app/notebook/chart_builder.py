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

# This decides how many individual categories torta/barras actually draw
# once generation proceeds (Story 7.4, extended to barras post-Epic-7 once
# multi-column combinations - Story 7.2 - made it easy to blow past the
# threshold with 80+ unique combinations) - the rest get folded into a
# single "Otros" slice/bar instead of rendering dozens of illegible slivers
# or bars.
#
# Deliberately equal to HIGH_CARDINALITY_THRESHOLD (post-Epic-7, user
# feedback): "Otros" should only ever kick in once the user has already seen
# the cardinality warning (Story 5.4) and clicked "Generar de todos modos"
# anyway - below the threshold, every category renders individually, since
# the user was never warned it might be a lot. Two independently-tuned
# numbers here used to leave a silent 9-15 zone where a chart bucketed
# categories the user had no idea were coming; tying them together closes
# that gap instead of just re-picking another arbitrary constant.
TOP_N_CATEGORIES_BEFORE_OTROS = HIGH_CARDINALITY_THRESHOLD


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
        series_expr = _limit_to_top_n_plus_others(series_expr, TOP_N_CATEGORIES_BEFORE_OTROS)
        # Epic 7 code review: groupby(level=0).sum() folds a real category
        # that happens to be named "Otros" together with the synthetic
        # bucket (pd.concat() alone would otherwise leave two same-labeled
        # entries) - applies to both chart types, since chart_builder.py
        # never sees real data and this must live in the generated
        # expression, same reasoning as _limit_to_top_n_plus_others itself.
        series_expr = f"{series_expr}.groupby(level=0, sort=False).sum()"
        if chart_type == "torta":
            # clip(lower=0) prevents a negative tail sum (e.g. a signed
            # "neto" column with more refunds than sales in the tail) from
            # raising matplotlib's "pie plot doesn't allow negative values" -
            # a pie chart has no meaningful way to show a negative slice, so
            # it's floored to zero instead of crashing. A bar CAN meaningfully
            # show a negative group total, so barras skips this.
            series_expr = f"{series_expr}.clip(lower=0)"
        # `_chart_data` names the final series once (instead of chaining
        # .plot.* directly onto the expression above) so the styling lines
        # below can reference it - both for its length (color count) and,
        # for torta, its index (legend labels) (user feedback: charts with
        # up to TOP_N_CATEGORIES_BEFORE_OTROS+1 long composite labels were
        # unreadable with matplotlib's flat single-color defaults).
        lines = [f"_chart_data = {series_expr}"]
        if chart_type == "torta":
            lines += [
                "_fig, _ax = plt.subplots(figsize=(11, 8))",
                "_wedges, _texts, _autotexts = _ax.pie("
                "_chart_data.values, labels=None, "
                "autopct=lambda p: f'{p:.1f}%' if p >= 3 else '', "
                "colors=plt.get_cmap('tab20').colors[:len(_chart_data)], pctdistance=0.8)",
                # Category names move to a side legend instead of on-slice
                # labels - with up to 16 long composite labels (Story 7.2),
                # on-slice labels stack and overlap into an unreadable mess.
                "_ax.legend(_wedges, _chart_data.index, loc='center left', "
                "bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)",
            ]
        else:
            lines += [
                "_ax = _chart_data.plot.bar(figsize=(10, 7), "
                "color=plt.get_cmap('tab20').colors[:len(_chart_data)])",
                # Plain thousands-separated numbers instead of matplotlib's
                # default "1e8"-style scientific notation on the y-axis.
                "_ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _pos: f'{x:,.0f}'))",
                # Long composite labels (Story 7.2) get truncated for the
                # x-axis specifically - this only changes the tick text, not
                # the underlying data/legend/exported values.
                "_ax.set_xticklabels(["
                "_t.get_text()[:28] + ('…' if len(_t.get_text()) > 28 else '') "
                "for _t in _ax.get_xticklabels()], rotation=45, ha='right')",
            ]
        lines.append(_bold_title_line(title))
        lines.append("plt.tight_layout()")
        return "\n".join(lines)

    if chart_type == "linea":
        column = columns[0]
        # astype(str) before parsing - a "fecha" column stored as a bare
        # integer YYYYMMDD (e.g. 20260602, the exact shape
        # excel_profiler.py's own DATE_YYYYMMDD_PATTERN already recognizes)
        # gets misparsed by pd.to_datetime() as nanoseconds-since-epoch when
        # passed the raw int, producing a garbage ~1970 date instead of the
        # real one - casting to str first (same pattern excel_profiler.py
        # itself uses to detect these columns) fixes it without changing
        # behavior for already-string or already-Timestamp columns.
        dates_expr = f"pd.to_datetime({variable}[{column!r}].astype(str), errors='coerce')"
        if value_column:
            series_expr = f"{variable}.groupby({dates_expr}.dt.date)[{value_column!r}].sum()"
            title = f"{value_column} por {column}"
        else:
            series_expr = f"{dates_expr}.value_counts().sort_index()"
            title = f"Cantidad de filas por {column}"
        return f"{series_expr}.plot.line()\n{_bold_title_line(title)}\nplt.tight_layout()"

    # histograma: distribution of a single numeric column, grouping columns ignored
    title = f"Distribución de {value_column}"
    return f"{variable}[{value_column!r}].plot.hist()\n{_bold_title_line(title)}\nplt.tight_layout()"


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


def _bold_title_line(title):
    """Shared styling for every chart type's title - bold, slightly larger
    than matplotlib's default, so the four chart types read as one
    consistent, professional-looking product instead of each carrying
    matplotlib's plain default title."""
    return f"plt.title({title!r}, fontsize=13, fontweight='bold')"


def _title_for(columns, value_column):
    label = columns[0] if len(columns) == 1 else ", ".join(columns)
    if value_column:
        return f"{value_column} por {label}"
    return f"Cantidad de filas por {label}"
