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

CHART_TYPES = {
    "torta", "barras", "linea", "histograma",
    # User feedback ("acaso no existen más [gráficas]?"): area/boxplot/heatmap
    # reuse the exact same {columns: categorica/fecha, value_column: numerica}
    # request shape the four original types already use - dispersion is the
    # one genuine exception (it needs two NUMERIC columns, no value_column;
    # see the "dispersion" branch below and the frontend's dedicated X/Y
    # selects, since its inputs don't fit the categorical-checkbox model).
    "area", "boxplot", "heatmap", "dispersion",
}

# Pie/bar charts become unreadable well before 20 slices; a time series or a
# histogram bins/aggregates automatically so cardinality of the raw column
# isn't a legibility problem for those - the check only applies here. boxplot
# and heatmap have the same "too many categories" legibility problem as
# torta/barras (a boxplot with 80 boxes, or an 80x80 heatmap grid, are just as
# illegible) - dispersion is exempt like linea/histograma: it plots individual
# numeric values, not category counts, so cardinality isn't the risk there.
HIGH_CARDINALITY_THRESHOLD = 15
_CARDINALITY_CHECK_TYPES = {"torta", "barras", "boxplot", "heatmap"}

# This decides how many individual categories torta/barras actually draw
# once generation proceeds (Story 7.4, extended to barras post-Epic-7 once
# multi-column combinations - Story 7.2 - made it easy to blow past the
# threshold with 80+ unique combinations) - the rest get folded into a
# single "Otros" slice/bar instead of rendering dozens of illegible slivers
# or bars. Deliberately torta/barras-only: boxplot/heatmap still get the
# cardinality WARNING above, but there's no sane way to "fold" a box-and-
# whisker distribution or a heatmap cell the way a pie/bar total can just be
# summed into one bucket - if the user forces generation anyway, they get
# every category, however cluttered.
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

# User feedback (real file: "detallado comfenalco"): a money column (neto,
# valor total, costo...) needs a "$" sign and Colombian-style "." thousands
# separator to actually read as currency - a plain quantity column (Cant,
# Consec) must NOT get a "$" prefix. excel_profiler.py has no concept of
# "this numeric column is money" (it only classifies categorica/numerica/
# fecha/descartable), so this is a substring heuristic on the column name,
# same trade-off the profiler itself already accepts elsewhere (e.g. its
# DATE_YYYYMMDD_PATTERN guesses "date" from shape, not a declared type) -
# imperfect but good enough without asking the user to tag every column.
#
# Duplicated in frontend/src/app/shared/money-format.ts (no shared module
# between the Python backend and the TypeScript frontend) - keep both
# keyword lists in sync if this one changes.
_MONEY_KEYWORDS = (
    "valor", "venta", "costo", "neto", "precio", "monto", "pago",
    "saldo", "ingreso", "egreso", "factura", "flete", "descuento",
    "iva", "bruto", "importe", "subtotal",
)


def _looks_like_money(column_name):
    """Real bug report (file: "relacion de facturas matecol.xlsx"): its own
    value column is literally named "N E T O" - one letter per cell joined
    with spaces (a two-row split header: a category row + a specific-field
    row, both real in that report). ' '.join('neto'.lower()) contains no
    space-free "neto" substring, so it silently never matched - the pie
    chart/tables built correctly but with zero money formatting, no error
    anywhere to notice. Stripping ALL whitespace before matching (not just
    trimming the ends) fixes this generically for any similarly space-split
    header, without ever creating a false match: no keyword below contains a
    space itself, so removing spaces from the candidate name can only turn a
    previously-missed match into a correct one, never the reverse."""
    if not column_name:
        return False
    lowered = "".join(column_name.lower().split())
    return any(keyword in lowered for keyword in _MONEY_KEYWORDS)


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
    that ignore it, e.g. histograma). Per-type column count/type
    requirements (all enforced by the caller - routes.py::generate_chart -
    before this function is reached, closed-set selection same as
    chart_type itself):

    - torta/barras: 1+ categorica/fecha columns, value_column optional.
    - linea: exactly 1 fecha column, value_column optional.
    - area: exactly 1 fecha column, value_column REQUIRED.
    - boxplot: exactly 1 categorica column, value_column REQUIRED.
    - heatmap: exactly 2 categorica columns, value_column REQUIRED.
    - dispersion: exactly 2 numerica columns (X, Y) carried in `columns` -
      value_column is unused for this one type (see the "dispersion" branch).
    - histograma: `columns` ignored entirely, value_column REQUIRED.

    Raises ValueError for an unrecognized chart_type - callers must already
    validate against CHART_TYPES before calling this (closed-set selection).
    """
    if chart_type not in CHART_TYPES:
        raise ValueError(f"Tipo de gráfica no reconocido: {chart_type!r}")

    if chart_type in ("torta", "barras"):
        is_money = _looks_like_money(value_column)
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
                # Every legend entry also carries its own percentage: the
                # on-slice autopct above only labels slices >=3% (to avoid
                # clutter), so a small slice's percentage would otherwise be
                # invisible everywhere - the legend is the one place it's
                # guaranteed legible no matter how small the slice or how
                # many categories there are (user feedback).
                "_total = _chart_data.sum()",
                # User feedback: "el 100% de qué?" - a bare "32.2%" doesn't
                # say what it's a share of. _pct_de is embedded via repr()
                # (value_column comes from user-uploaded Excel content) as
                # its own generated-code line, then referenced by name in
                # the f-string below - not interpolated as literal text -
                # so a stray quote in the column name can't break the
                # generated code's syntax.
                f"_pct_de = {(value_column or 'la cantidad de filas')!r}",
                # User feedback: the percentage alone doesn't say the actual
                # amount ("38.6% de neto, pero ¿cuánto es neto?") - val is
                # already the slice's real total, so show it too. When the
                # value column looks like money (_looks_like_money), format
                # it as Colombian pesos: "$ " prefix (matching the frontend's
                # es-CO `currency` pipe pattern, "¤ #,##0.00") + "." as the
                # thousands separator (built from the same :,.0f as before, then
                # .replace(',', '.') - simpler and more robust than reaching
                # for Python's locale module inside the sandboxed worker,
                # whose system locale isn't guaranteed to be es_CO). A
                # non-money numeric column (e.g. a quantity) keeps the exact
                # prior plain format - unchanged.
                (
                    "_fmt_valor = lambda v: '$ ' + f'{v:,.0f}'.replace(',', '.')"
                    if is_money
                    else "_fmt_valor = lambda v: f'{v:,.0f}'"
                ),
                "_ax.legend(_wedges, "
                "[f'{name} - {_fmt_valor(val)} ({val / _total * 100:.1f}%) de {_pct_de}' "
                "for name, val in _chart_data.items()], "
                "loc='center left', bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)",
            ]
        else:
            lines += [
                "_ax = _chart_data.plot.bar(figsize=(10, 7), "
                "color=plt.get_cmap('tab20').colors[:len(_chart_data)])",
                # Plain thousands-separated numbers instead of matplotlib's
                # default "1e8"-style scientific notation on the y-axis -
                # same money-detection and Colombian-punctuation treatment as
                # the torta legend above, for the same reason.
                "_ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _pos: "
                + ("\"$ \" + f'{x:,.0f}'.replace(',', '.')" if is_money else "f'{x:,.0f}'")
                + "))",
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
        dates_expr = _date_series_expr(variable, column)
        if value_column:
            # dt.floor('D') (not dt.date) - keeps a real pandas
            # Timestamp/DatetimeIndex, so matplotlib's date-aware tick
            # locator auto-spaces and formats the x-axis (user feedback:
            # dt.date produced plain Python date objects, treated as
            # generic categorical ticks - every single date drawn,
            # unrotated, overlapping into unreadable text with a few dozen
            # days of data).
            series_expr = f"{variable}.groupby({dates_expr}.dt.floor('D'))[{value_column!r}].sum()"
            title = f"{value_column} por {column}"
            ylabel = value_column
        else:
            series_expr = f"{dates_expr}.value_counts().sort_index()"
            title = f"Cantidad de filas por {column}"
            ylabel = "Cantidad de filas"
        return (
            f"_ax = {series_expr}.plot.line(figsize=(10, 6))\n"
            f"_ax.set_ylabel({ylabel!r})\n"
            f"{_bold_title_line(title)}\n"
            "plt.tight_layout()"
        )

    if chart_type == "area":
        # Required value_column (unlike linea, where it's optional): a
        # count-mode area chart ("cantidad de filas por fecha") would be
        # visually identical to linea's own count mode - area's only reason
        # to exist as a separate type is showing a summed value filled in,
        # so it requires the input that makes that distinct (caller must
        # enforce this before calling - routes.py's generate_chart).
        column = columns[0]
        dates_expr = _date_series_expr(variable, column)
        series_expr = f"{variable}.groupby({dates_expr}.dt.floor('D'))[{value_column!r}].sum()"
        is_money = _looks_like_money(value_column)
        formatter_expr = "\"$ \" + f'{y:,.0f}'.replace(',', '.')" if is_money else "f'{y:,.0f}'"
        return (
            f"_ax = {series_expr}.plot.area(figsize=(10, 6), alpha=0.6, "
            "color=plt.get_cmap('tab20').colors[0])\n"
            f"_ax.set_ylabel({value_column!r})\n"
            "_ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _pos: " + formatter_expr + "))\n"
            f"{_bold_title_line(f'{value_column} por {column} (área)')}\n"
            "plt.tight_layout()"
        )

    if chart_type == "boxplot":
        # Exactly 1 categorical column (caller-enforced) + a required
        # numeric value_column - there's no meaningful "count rows" mode for
        # a box-and-whisker plot. Uses seaborn (already preloaded by
        # execution.py's build_namespace() for every cell) rather than
        # pandas' own df.boxplot(), which needs a MultiIndex/groupby dance to
        # get one box per category - sns.boxplot(x=, y=) does it directly.
        # NaN group values are silently dropped by seaborn's default -
        # unlike torta/barras' explicit "(vacío)" bucket (_grouping_expr),
        # deliberately not replicated here to keep this first pass simple.
        column = columns[0]
        is_money = _looks_like_money(value_column)
        formatter_expr = "\"$ \" + f'{y:,.0f}'.replace(',', '.')" if is_money else "f'{y:,.0f}'"
        return (
            "_fig, _ax = plt.subplots(figsize=(10, 7))\n"
            f"sns.boxplot(data={variable}, x={column!r}, y={value_column!r}, "
            f"hue={column!r}, palette='tab20', legend=False, ax=_ax)\n"
            "_ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _pos: " + formatter_expr + "))\n"
            "_ax.set_xticklabels([_t.get_text()[:28] + ('…' if len(_t.get_text()) > 28 else '') "
            "for _t in _ax.get_xticklabels()], rotation=45, ha='right')\n"
            f"{_bold_title_line(f'Distribución de {value_column} por {column}')}\n"
            "plt.tight_layout()"
        )

    if chart_type == "heatmap":
        # Exactly 2 categorical columns (caller-enforced) + a required
        # numeric value_column, summed into a pivot table (rows x cols).
        # Cell annotations use a plain ',.0f' format (comma thousands, no
        # "$" prefix, no Colombian punctuation) - seaborn's `fmt` is a bare
        # format-spec string applied per-cell internally, not a callable, so
        # the _looks_like_money() treatment used elsewhere in this module
        # can't be reused here without pre-formatting every cell into its
        # own annotation array; left as a known simplification for this
        # first pass rather than adding that complexity up front.
        row_col, col_col = columns[0], columns[1]
        pivot_expr = (
            f"{variable}.pivot_table(index={row_col!r}, columns={col_col!r}, "
            f"values={value_column!r}, aggfunc='sum', fill_value=0)"
        )
        return (
            f"_pivot = {pivot_expr}\n"
            "_fig, _ax = plt.subplots(figsize=(10, 8))\n"
            "sns.heatmap(_pivot, annot=True, fmt=',.0f', cmap='YlGnBu', ax=_ax)\n"
            f"{_bold_title_line(f'{value_column} por {row_col} y {col_col}')}\n"
            "plt.tight_layout()"
        )

    if chart_type == "dispersion":
        # The one chart type that doesn't fit {columns: categorica/fecha,
        # value_column: numerica} - it needs two NUMERIC columns (X, Y), so
        # both travel in `columns` (caller-enforced: exactly 2, both
        # numerica) and value_column is unused. No cardinality check/Otros
        # bucketing applies (see _CARDINALITY_CHECK_TYPES) - a scatter of
        # individual points scales visually with density, not category count.
        x_col, y_col = columns[0], columns[1]
        return (
            "_fig, _ax = plt.subplots(figsize=(9, 7))\n"
            f"_ax.scatter({variable}[{x_col!r}], {variable}[{y_col!r}], "
            "alpha=0.6, color=plt.get_cmap('tab20').colors[0])\n"
            f"_ax.set_xlabel({x_col!r})\n"
            f"_ax.set_ylabel({y_col!r})\n"
            f"{_bold_title_line(f'{y_col} vs {x_col}')}\n"
            "plt.tight_layout()"
        )

    # histograma: distribution of a single numeric column, grouping columns ignored
    title = f"Distribución de {value_column}"
    return f"{variable}[{value_column!r}].plot.hist()\n{_bold_title_line(title)}\nplt.tight_layout()"


def _date_series_expr(variable, column):
    """astype(str) before parsing - a "fecha" column stored as a bare
    integer YYYYMMDD (e.g. 20260602, the exact shape excel_profiler.py's own
    DATE_YYYYMMDD_PATTERN already recognizes) gets misparsed by
    pd.to_datetime() as nanoseconds-since-epoch when passed the raw int,
    producing a garbage ~1970 date instead of the real one - casting to str
    first (same pattern excel_profiler.py itself uses to detect these
    columns) fixes it without changing behavior for already-string or
    already-Timestamp columns. Shared by linea and area - both plot a date
    column on the x-axis."""
    return f"pd.to_datetime({variable}[{column!r}].astype(str), errors='coerce')"


def _grouping_expr(variable, columns):
    """What to group by: the column name directly when there's one, or a
    "composite key" joined as a string when there's more than one - avoids
    matplotlib rendering raw Python-tuple labels (e.g. "('V0', 'Enero')")
    on the chart's axis/legend.

    Note: chart_builder.py's own _grouped_series_expr() bypasses this
    single-column branch entirely (it hardcodes `{variable}.groupby({col!r})`
    directly, guarding Story 7.2 AC3's byte-identical-to-pre-7.2 guarantee) -
    this branch is only reachable via table_builder.py (Epic 8), which calls
    _grouping_expr() unconditionally for every column count. Confirmed via
    the test suite: no chart_builder.py test exercises this branch.
    """
    if len(columns) == 1:
        # fillna() before use - otherwise pandas groupby(dropna=True, the
        # default) silently drops every row whose grouping column is null,
        # understating totals/percentages with no indication to the user a
        # row was excluded (Epic 8 code review) - same reasoning as the
        # multi-column branch below, just newly reachable here since chart
        # generation itself never exercises this single-column branch.
        return f"{variable}[{columns[0]!r}].fillna('(vacío)')"
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
