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
    column, not a narrowed view) by a single value column, and add the same
    '% del total'/'% acumulado' columns the grouped summary (build_summary_code)
    already has - computed per row instead of per group (user feedback: a
    "detailed" view where grouping isn't required, with the same percentage
    columns explained the same way). The row-count cap already applied by
    execution.py's DataFrame capture (the same one df.head() already
    respects) covers truncation - nothing extra here."""
    lines = [
        f"_ordenado = {variable}.sort_values({value_column!r}, ascending={bool(ascending)!r})",
        f"_total = {variable}[{value_column!r}].sum()",
        # Same zero-total guard as build_summary_code (Epic 8 code review) -
        # a signed value_column whose rows cancel out to exactly zero would
        # otherwise leak "inf"/"nan" text into the table.
        f"_pct = (_ordenado[{value_column!r}] / _total * 100)"
        ".round(1).replace([float('inf'), float('-inf')], 0).fillna(0)",
        "_acum = _pct.cumsum().round(1)",
        # Bare expression, not assigned to a variable - execution.py only
        # captures the LAST expression statement of a cell as the result.
        "_ordenado.assign(**{'% del total': _pct, '% acumulado': _acum})",
    ]
    return "\n".join(lines)


def _pareto_marker_lines(variable, grouping, value_column):
    """Code lines that compute _t (group totals, sorted descending), '% del
    total' (_pct), '% acumulado' (_acum), and the 80/20 marker column
    (_marca) - shared by build_summary_code and build_summary_detail_code so
    the crossing-row-counting logic (and its code-review-caught off-by-one
    fix, see the comment below) can't quietly diverge between the two."""
    return [
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
        # Code review fix: _cruce is every row FROM the crossing point
        # onward (the tail, since _acum keeps climbing to 100% after
        # crossing 80%) - len(_cruce) is NOT "how many top categories are
        # needed to reach 80%". The rank of the crossing row (categories
        # counted from the top down to and including it) is instead the
        # count of rows that HADN'T yet reached 80%, plus the crossing row
        # itself.
        "    _n_cruce = int((_acum < 80).sum()) + 1",
        # User feedback: a single arrow on one row, buried dozens of rows
        # deep in a real table with 80+ categories, was easy to miss or
        # misread out of context. Every row from the top through the
        # crossing row now gets a checkmark too, so "these together are the
        # 80%" reads as one visually obvious block - the crossing row itself
        # keeps a distinct label so the exact threshold is still called out.
        "    _marca.iloc[:_n_cruce] = '✓'",
        "    _marca.iloc[_n_cruce - 1] = '✓ ← 80% aquí'",
        "    _pct_cruce = _cruce.iloc[0]",
        "    _n_total = len(_acum)",
        "    _palabra = 'categoría concentra' if _n_cruce == 1 else 'categorías concentran'",
        "    print(f'{_n_cruce} de {_n_total} {_palabra} el {_pct_cruce:.0f}% del total.')",
    ]


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
    lines = _pareto_marker_lines(variable, grouping, value_column) + [
        # Bare expression, not assigned to a variable - execution.py only
        # captures the LAST expression statement of a cell as the result;
        # an assignment here would leave result_html as None. The `if`
        # block above is a separate top-level statement, so it doesn't
        # affect this still being the cell's final expression.
        f"pd.DataFrame({{{value_column!r}: _t, '% del total': _pct, '% acumulado': _acum, '80/20': _marca}})",
    ]
    return "\n".join(lines)


def build_summary_detail_code(variable, columns, value_column):
    """User feedback on the grouped summary (build_summary_code): "faltaria
    un resumen detallado, en el que por ejemplo salga LATIN LOGISTICS
    COLOMBIA S.A.S. las n veces" - the aggregate total per group isn't
    enough, they also want every individual row that makes up that total.

    Shape: one subtotal ("... — TOTAL") row per group, immediately followed
    by that group's own rows sorted by value_column descending, with a
    '% de su grupo' column (each row's share of ITS OWN group's total, not
    the grand total - build_summary_code already covers "share of the grand
    total"). Groups themselves are ordered by group total descending, same
    as build_summary_code, so the biggest group's block appears first - the
    "como un Excel con subtotales" shape the user asked for.

    Reuses chart_builder._grouping_expr() for the same reason build_summary_code
    does - single source of truth for the single-vs-multi-column / composite-key
    / fillna('(vacío)') logic. Also reuses _pareto_marker_lines() (bug report:
    checking "Mostrar detalle" was silently dropping the 80/20 analysis the
    aggregate summary already had) - the marker/'% del total'/'% acumulado'
    are GROUP-level metrics, so they're attached to each group's "— TOTAL"
    row only, never to the individual rows underneath it (which carry their
    own row-level '% de su grupo' instead).
    """
    grouping = _grouping_expr(variable, columns)
    lines = _pareto_marker_lines(variable, grouping, value_column) + [
        f"_grupo = {grouping}",
        f"_total_grupo = {variable}.groupby(_grupo)[{value_column!r}].transform('sum')",
        # Same zero-total guard as build_summary_code/build_sort_code - a
        # group whose rows cancel out to exactly zero (e.g. a 'saldo'
        # column) would otherwise leak inf/nan into '% de su grupo'.
        f"_pct_grupo = ({variable}[{value_column!r}] / _total_grupo * 100)"
        ".round(1).replace([float('inf'), float('-inf')], 0).fillna(0)",
        f"_detalle = {variable}.assign(**{{'Grupo': _grupo, '% de su grupo': _pct_grupo}})",
        # Categorical (not plain sort_values on the string column) so groups
        # stay ordered by TOTAL descending (same order _t already has), not
        # alphabetically - matches build_summary_code's ordering.
        "_detalle['Grupo'] = pd.Categorical(_detalle['Grupo'], categories=_t.index, ordered=True)",
        f"_detalle = _detalle.sort_values(['Grupo', {value_column!r}], ascending=[True, False])",
        f"_filas_subtot = pd.DataFrame({{"
        f"'Grupo': [f'{{g}} — TOTAL' for g in _t.index], {value_column!r}: _t.values, "
        "'% del total': _pct.values, '% acumulado': _acum.values, '80/20': _marca.values})",
        "_filas_subtot['__orden__'] = range(len(_t))",
        "_filas_subtot['__es_total__'] = True",
        "_detalle['__orden__'] = _detalle['Grupo'].map({g: i for i, g in enumerate(_t.index)})",
        "_detalle['__es_total__'] = False",
        "_final = pd.concat([_filas_subtot, _detalle], ignore_index=True)",
        # Bare expression, not assigned to a variable - execution.py only
        # captures the LAST expression statement of a cell as the result.
        "_final.sort_values(['__orden__', '__es_total__'], ascending=[True, False])"
        ".drop(columns=['__orden__', '__es_total__'])",
    ]
    return "\n".join(lines)
