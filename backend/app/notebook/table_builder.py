"""Builds a Python code string for the no-code table flow (Story 8.1;
grouped summary + Pareto highlight added in Story 8.2/8.3).

Same security/execution principles as chart_builder.py: a closed set of
columns already validated by excel_profiler (Epic 4), embedded via repr(),
never free-form text - executed via the same WorkerManager.execute() path,
so CELL_TIMEOUT_SECONDS and the existing DataFrame -> HTML capture
(execution.py::_capture_value(), already used by the free notebook's
df.head()) come for free. No new execution or rendering mechanism needed.
"""
from app.notebook.chart_builder import _grouping_expr


def build_sort_code(variable, value_column, ascending):
    """Sort every row (all columns kept, not a projection down to just
    value_column - the user asked to see the whole record ordered by a
    column, not a narrowed view) by a single value column. The row-count
    cap already applied by execution.py's DataFrame capture (the same one
    df.head() already respects) covers truncation - nothing extra here."""
    return f"{variable}.sort_values({value_column!r}, ascending={bool(ascending)!r})"


def build_summary_code(variable, columns, value_column):
    """Group by column(s), sum a value column, and compute each group's
    share of the total plus a running cumulative share (sorted descending)
    - answers "who concentrates the value" (Story 8.2) directly, and marks
    the exact row where the cumulative share first reaches 80% (Story 8.3,
    Pareto) with a plain-text column instead of a pandas Styler background
    color - a Styler isn't a DataFrame/Series, so execution.py's existing
    _capture_value() wouldn't know how to render it without being extended;
    a text column needs zero changes there.

    Reuses chart_builder._grouping_expr() rather than duplicating the
    single-vs-multiple-column / composite-key-join / fillna('(vacío)')
    logic it already established and tested - so the two modules can't
    quietly diverge on how a composite key is built.

    Simplification (documented, not handled): assumes value_column sums are
    non-negative, so the cumulative share is monotonically increasing (the
    typical case - invoice/client totals). A heavily mixed-sign value_column
    could make "where it crosses 80%" less intuitive - out of scope here,
    same risk tolerance as the rest of this epic.
    """
    grouping = _grouping_expr(variable, columns)
    lines = [
        f"_t = {variable}.groupby({grouping})[{value_column!r}].sum().sort_values(ascending=False)",
        # A signed value_column can make group totals cancel out to exactly
        # zero (e.g. a "saldo" column with equal and opposite balances) -
        # dividing by a zero total produces +/-inf, and cumsum() of that
        # produces NaN, which would otherwise leak as literal "inf"/"nan"
        # text into the table and the printed sentence below. Replace/fillna
        # degrades this degenerate case to a plain 0% instead.
        "_pct = (_t / _t.sum() * 100).round(1).replace([float('inf'), float('-inf')], 0).fillna(0)",
        "_acum = _pct.cumsum().round(1)",
        "_marca = pd.Series([''] * len(_acum), index=_acum.index)",
        "_cruce = _acum[_acum >= 80]",
        "if len(_cruce) > 0:",
        "    _marca[_cruce.index[0]] = '← aquí se cruza el 80%'",
        # Code review fix: _cruce is every row FROM the crossing point
        # onward (the tail, since _acum keeps climbing to 100% after
        # crossing 80%) - len(_cruce) is NOT "how many top categories are
        # needed to reach 80%". The rank of the crossing row (categories
        # counted from the top down to and including it) is instead the
        # count of rows that HADN'T yet reached 80%, plus the crossing row
        # itself.
        "    _n_cruce = int((_acum < 80).sum()) + 1",
        "    _pct_cruce = _cruce.iloc[0]",
        "    _n_total = len(_acum)",
        "    _palabra = 'categoría concentra' if _n_cruce == 1 else 'categorías concentran'",
        "    print(f'{_n_cruce} de {_n_total} {_palabra} el {_pct_cruce:.0f}% del total.')",
        # Bare expression, not assigned to a variable - execution.py only
        # captures the LAST expression statement of a cell as the result;
        # an assignment here would leave result_html as None. The `if`
        # block above is a separate top-level statement, so it doesn't
        # affect this still being the cell's final expression.
        f"pd.DataFrame({{{value_column!r}: _t, '% del total': _pct, '% acumulado': _acum, '80/20': _marca}})",
    ]
    return "\n".join(lines)
