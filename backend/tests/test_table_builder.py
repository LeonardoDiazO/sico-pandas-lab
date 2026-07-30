import ast

from app.notebook.chart_builder import HIGH_CARDINALITY_THRESHOLD
from app.notebook.table_builder import (
    build_column_values_code,
    build_summary_code,
    build_summary_detail_code,
    build_sort_code,
)


def _assert_valid_python(code):
    ast.parse(code)  # raises SyntaxError if the generated code is malformed


def test_sort_descending_by_default_shape():
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert "sort_values('neto', ascending=False)" in code


def test_sort_ascending():
    code = build_sort_code("df", "neto", True)
    _assert_valid_python(code)
    assert "sort_values('neto', ascending=True)" in code


def test_sort_includes_percentage_of_total_and_cumulative_percentage():
    """User feedback: "detallado en la que la agrupación ya no sea
    necesaria" + "explicar mejor el porcentaje" - the raw (ungrouped) sort
    view now carries the same '% del total'/'% acumulado' columns the
    grouped summary (Story 8.2) already has, computed over every row
    individually instead of per group."""
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert "% del total" in code
    assert "% acumulado" in code
    assert "cumsum()" in code


def test_sort_last_line_is_a_bare_expression_not_an_assignment():
    code = build_sort_code("df", "neto", False)
    last_line = code.strip().splitlines()[-1]
    assert not last_line.startswith("_ordenado =")
    assert "assign(" in last_line


def test_sort_zero_total_does_not_produce_inf_or_nan():
    """Same degenerate case already fixed for the grouped summary (Story
    8.2/8.3 code review): a signed value column whose rows cancel out to
    exactly zero must not leak 'inf'/'nan' into the table."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "B"], "saldo": [1000.0, -1000.0]})
    code = build_sort_code("df", "saldo", False)
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "inf" not in result["result_html"]
    assert "nan" not in result["result_html"]


def test_column_name_with_a_single_quote_does_not_break_generated_syntax():
    """Column names come from user-uploaded Excel content - repr() must be
    used to embed them, not manual string concatenation (same security
    pattern already established by chart_builder.py)."""
    code = build_sort_code("df", "vendor's net", False)
    _assert_valid_python(code)


def test_sort_formats_money_column_as_colombian_pesos():
    """User feedback: "en esta parte de ordenar tabla no está colocando los
    valores en peso colombiano" - a money value column (e.g. 'neto') must
    display as "$ 1.234.567" in the sorted table, same treatment
    chart_builder.py already applies to chart legends/axes. The sort/%
    columns above (computed from the real numeric _ordenado[value_column])
    must stay correct - only the DISPLAYED value_column changes."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"cliente": ["A", "B", "C"], "neto": [50.0, 200.0, 1234567.0]}
    )
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert "'$ ' + f'{v:,.0f}'.replace(',', '.')" in code

    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert ">$ 1.234.567<" in html
    assert ">$ 200<" in html
    assert ">$ 50<" in html
    # the % columns must still be computed from the real numeric values, not
    # from the money-formatted strings (would otherwise raise/produce garbage)
    assert "inf" not in html
    assert "nan" not in html


def test_sort_leaves_non_money_column_formatting_unchanged():
    code = build_sort_code("df", "cantidad", False)
    _assert_valid_python(code)
    assert "$" not in code


def test_sort_runs_end_to_end_against_a_real_dataframe():
    """Empirical verification (same standard as Epic 7's review), not just a
    string assertion - executes the generated code against a synthetic
    DataFrame via the real execution.py pipeline and checks the actual
    resulting order."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"cliente": ["A", "B", "C"], "neto": [50.0, 200.0, 100.0]}
    )
    code = build_sort_code("df", "neto", False)
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["result_html"] is not None
    # descending: B (200) first, then C (100), then A (50)
    idx_b = result["result_html"].index(">B<")
    idx_c = result["result_html"].index(">C<")
    idx_a = result["result_html"].index(">A<")
    assert idx_b < idx_c < idx_a
    # total = 350 -> B=57.1%(cum 57.1), C=28.6%(cum 85.7), A=14.3%(cum 100.0)
    row_b = result["result_html"][idx_b : result["result_html"].index("</tr>", idx_b)]
    cells_b = [c for c in row_b.split("<td>")[1:]]
    assert "57.1</td>" in cells_b[1]
    assert "100.0" not in row_b  # sanity: B is not the last cumulative row


# --- Story 8.2: grouped summary with % of total and cumulative % ----------


def test_summary_single_column_shape():
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    # .fillna('(vacío)') on the grouping column - Epic 8 code review: a
    # single-column groupby with no null handling used to silently drop
    # rows with a null category, understating the total (see
    # test_summary_single_column_with_null_category_does_not_drop_rows).
    assert "groupby(df['cliente'].fillna('(vacío)'))" in code
    assert "['neto']" in code
    assert "% del total" in code
    assert "% acumulado" in code
    assert "cumsum()" in code


def test_summary_single_column_with_null_category_does_not_drop_rows():
    """Code review regression: pandas groupby(dropna=True, the default)
    silently drops rows whose grouping column is null - understating the
    total/percentages with no indication to the user. fillna() before
    grouping keeps them under a '(vacío)' bucket instead, same as the
    multi-column composite-key path already did."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "B", None], "neto": [100.0, 200.0, 50.0]})
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "(vacío)" in result["result_html"]
    # the total across all 3 rows (350.0) must be reflected in the
    # percentages, not just the 2 non-null rows (300.0). "neto" is money
    # (_looks_like_money), so its displayed value is "$ 50", not "50.0".
    assert ">$ 50<" in result["result_html"]


def test_summary_multiple_columns_uses_composite_grouping_key():
    """Reuses chart_builder._grouping_expr() - must not diverge from the
    exact composite-key logic (join separator, fillna for nulls) already
    established and tested there."""
    code = build_summary_code("df", ["cliente", "mes"], "neto")
    _assert_valid_python(code)
    assert ".astype(str).agg(' - '.join, axis=1)" in code
    assert "fillna('(vacío)')" in code


def test_summary_last_line_is_a_bare_expression_not_an_assignment():
    """execution.py only captures the LAST expression statement (ast.Expr)
    of a cell as the result - if the DataFrame were assigned to a variable
    on the last line instead, result_html would stay None."""
    code = build_summary_code("df", ["cliente"], "neto")
    last_line = code.strip().splitlines()[-1]
    assert not last_line.startswith("_") or "=" not in last_line.split("(")[0]
    assert last_line.startswith("pd.DataFrame(")


def test_summary_column_name_with_a_single_quote_does_not_break_generated_syntax():
    code = build_summary_code("df", ["vendor's code"], "amount's")
    _assert_valid_python(code)


def test_summary_runs_end_to_end_and_percentages_sum_to_roughly_100():
    """Empirical verification (same standard as Epic 7's review) - executes
    the generated code against a synthetic DataFrame via the real
    execution.py pipeline and checks the actual computed percentages, not
    just that the code parses."""
    import re

    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B", "C", "C", "C"],
            "neto": [100.0, 100.0, 300.0, 200.0, 200.0, 100.0],
        }
    )
    # totals per client: A=200, B=300, C=500 -> total=1000
    # sorted desc: C (50%), B (30%), A (20%) -> cumulative: 50, 80, 100
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert html is not None

    percentages = [float(m) for m in re.findall(r'<td[^>]*>(\d+\.\d)</td>', html)]
    # 3 groups x 2 numeric columns (% del total, % acumulado) = 6 cells.
    # "neto" is money (_looks_like_money) - its own cells render as "$ 200"
    # (no decimal point via :,.0f), so they never match this digit.digit
    # pattern - only the percentage columns do.
    assert len(percentages) == 6
    # "% acumulado" is the 3rd <td> in each row (neto, % del total, % acumulado, ...)
    row_c = html[html.index(">C<") : html.index("</tr>", html.index(">C<"))]
    cells_c = re.findall(r"<td[^>]*>([^<]*)</td>", row_c)
    assert cells_c[0] == "$ 500"  # neto total for C, Colombian-formatted pesos
    assert float(cells_c[2]) == 50.0


# --- Story 8.3: highlight where the cumulative % crosses 80% (Pareto) -----


def test_summary_includes_80_20_marker_column():
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "'80/20'" in code
    assert "_acum[_acum >= 80]" in code


def test_summary_last_line_is_still_a_bare_expression_after_marker_added():
    """Regression guard (Story 8.2's invariant must survive Story 8.3's
    extension): the if-block that computes the marker/prints the insight is
    a separate top-level statement before the final expression - it must
    not turn the DataFrame construction into something execution.py's
    last-expression capture would miss."""
    code = build_summary_code("df", ["cliente"], "neto")
    last_line = code.strip().splitlines()[-1]
    assert last_line.startswith("pd.DataFrame(")
    assert "'80/20': _marca" in last_line


def test_summary_prints_plain_language_pareto_insight():
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "print(f'{_n_cruce} de {_n_total} {_palabra} el {_pct_cruce:.0f}% del total.')" in code


def test_summary_pareto_runs_end_to_end_marks_the_right_row_and_prints_insight():
    """Empirical verification (same standard as Epic 7's review) - executes
    the generated code against a synthetic DataFrame and checks both the
    marker landed on the correct row AND the printed sentence has the
    correct numbers, not just that the code parses."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B", "C", "C", "C", "D"],
            "neto": [100.0, 100.0, 300.0, 200.0, 200.0, 100.0, 50.0],
        }
    )
    # totals: C=500 (47.6%), B=300 (28.6%), A=200 (19.0%), D=50 (4.8%) -> total=1050
    # sorted desc: C(cum 47.6), B(cum 76.2), A(cum 95.2), D(cum 100.0)
    # crossing row is A (3rd) - the correct insight is "3 of 4 categories
    # concentrate ~95%", i.e. counted from the TOP down to and including the
    # crossing row, not from the crossing row to the end (that would wrongly
    # say "2 de 4" - regression-tests the code-review-caught counting bug).
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert html is not None
    assert html.count("✓ ← 80% aquí") == 1

    stdout = result["stdout"]
    assert "3 de 4" in stdout
    assert "95% del total." in stdout


def test_summary_with_zero_groups_does_not_crash_or_print_anything():
    """AC3 edge case: an empty grouping (e.g. a filtered-to-nothing
    DataFrame) must not raise - no crossing row exists, so no marker and no
    print, but the table (empty) still renders."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": [], "neto": []})
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["stdout"] == ""


def test_summary_pareto_count_is_correct_when_crossing_happens_on_the_last_row():
    """Code review regression test: values [500, 290, 210] sorted descending
    give cumulative % of 50, 79, 100 - the 80% crossing happens on the LAST
    (smallest) row. The correct insight is "3 de 3 categorías concentran el
    100% del total" (all three are needed) - the pre-fix bug computed
    len(_cruce) = 1 here (only the trailing row itself), which would have
    printed the nonsensical "1 de 3 categoría concentra el 100% del total."
    as if the single smallest category alone explained the whole total."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"cliente": ["A", "B", "C"], "neto": [500.0, 290.0, 210.0]}
    )
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "3 de 3" in result["stdout"]
    assert "100% del total." in result["stdout"]


def test_summary_zero_total_does_not_produce_inf_or_nan():
    """Code review regression: a signed value column whose group totals
    cancel out to exactly zero (e.g. a 'saldo' column with equal and
    opposite balances) makes `_t.sum() == 0`, so a naive percentage
    division produces +/-inf, and cumsum of inf values produces NaN -
    which used to render as the literal text 'inf'/'nan' directly in the
    table and the printed sentence. Must degrade to 0% instead of leaking
    that arithmetic garbage to the user."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "B"], "saldo": [1000.0, -1000.0]})
    code = build_summary_code("df", ["cliente"], "saldo")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "inf" not in result["result_html"]
    assert "nan" not in result["result_html"]
    assert "inf" not in result["stdout"]


def test_summary_pareto_matches_the_canonical_abcde_example():
    """Reference example the user gave directly (A/B/C/D/E clients,
    $50k/$20k/$15k/$10k/$5k) - A+B+C = 85% of the $100k total, so exactly 3
    of 5 clients are needed to cross 80%. Locks in this exact worked example
    as a permanent regression case, same role the Matecol fixture plays for
    excel_profiler.py."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "B", "C", "D", "E"],
            "facturacion": [50000, 20000, 15000, 10000, 5000],
        }
    )
    code = build_summary_code("df", ["cliente"], "facturacion")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["stdout"] == "3 de 5 categorías concentran el 85% del total.\n"
    html = result["result_html"]
    assert html.count("✓ ← 80% aquí") == 1
    # User feedback: a single arrow buried in a long table (80+ real rows)
    # was easy to miss/misread - every row from the top through the
    # crossing row now gets a plain checkmark too, so the "top 80%" reads
    # as one visually obvious block instead of one lonely marker.
    row_a = html[html.index(">A<") : html.index("</tr>", html.index(">A<"))]
    row_b = html[html.index(">B<") : html.index("</tr>", html.index(">B<"))]
    row_d = html[html.index(">D<") : html.index("</tr>", html.index(">D<"))]
    row_e = html[html.index(">E<") : html.index("</tr>", html.index(">E<"))]
    assert "✓" in row_a and "80%" not in row_a
    assert "✓" in row_b and "80%" not in row_b
    assert "✓" not in row_d
    assert "✓" not in row_e


# --- "Resumen detallado": drill into each group's individual rows ---------


def test_detail_last_line_is_a_bare_expression_not_an_assignment():
    """Uses a non-money value column ("cantidad") deliberately - this test is
    about the bare-expression/no-assignment structural invariant, not about
    money formatting (see test_detail_money_column_final_line_formats_pesos
    below for that). _final itself (built via the plain .drop(columns=...)
    chain, assigned on the second-to-last line) is the bare final expression
    in the non-money case."""
    code = build_summary_detail_code("df", ["cliente"], "cantidad")
    _assert_valid_python(code)
    lines = code.strip().splitlines()
    assert lines[-1] == "_final"
    assert "drop(columns=" in lines[-2]


def test_detail_money_column_final_line_formats_pesos():
    """A money value column (e.g. 'neto') gets its own final line: the plain
    .drop(columns=...) chain is assigned to _final first, then the bare
    expression becomes _final.assign(...) with the money-formatted column -
    still a bare expression (execution.py needs the last statement to be one
    to capture result_html), just a different final line than the non-money
    case above."""
    code = build_summary_detail_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    last_line = code.strip().splitlines()[-1]
    assert last_line.startswith("_final.assign(")
    assert "'$ ' + f'{v:,.0f}'.replace(',', '.')" in last_line


def test_detail_includes_percentage_of_its_own_group():
    code = build_summary_detail_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "% de su grupo" in code


def test_detail_column_name_with_a_single_quote_does_not_break_generated_syntax():
    code = build_summary_detail_code("df", ["vendor's code"], "amount's")
    _assert_valid_python(code)


def test_detail_runs_end_to_end_one_subtotal_row_per_group_then_its_own_rows():
    """Empirical verification against the real execution.py pipeline: each
    group gets exactly one 'TOTAL' row, followed by its own individual rows
    sorted by value descending, groups ordered by total descending - the
    "como un Excel con subtotales" shape the user asked for."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["LATIN", "OL GROUP", "LATIN", "LATIN", "OL GROUP"],
            "factura": ["F1", "F2", "F3", "F4", "F5"],
            "neto": [1000.0, 500.0, 2000.0, 300.0, 700.0],
        }
    )
    code = build_summary_detail_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert html is not None
    # LATIN's total (3300) is bigger than OL GROUP's (1200) -> LATIN's block comes first
    assert html.index("LATIN") < html.index("OL GROUP")
    assert html.count("TOTAL") == 2
    # within LATIN's block, individual rows appear in value-descending order
    # (2000, 1000, 300) - "neto" is money, so displayed as Colombian pesos.
    idx_total = html.index("LATIN — TOTAL")
    idx_2000 = html.index(">$ 2.000<")
    idx_1000 = html.index(">$ 1.000<")
    idx_300 = html.index(">$ 300<")
    assert idx_total < idx_2000 < idx_1000 < idx_300
    # LATIN's 3 individual invoices all show up as separate rows (the user's
    # literal ask: "que salga LATIN LOGISTICS ... las n veces")
    assert ">F1<" in html and ">F3<" in html and ">F4<" in html


def test_detail_percentage_of_group_is_correct_not_percentage_of_grand_total():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"cliente": ["A", "A"], "neto": [300.0, 100.0]}
    )
    code = build_summary_detail_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    # 300 is 75% of A's own total (400), not of some larger grand total
    assert ">75.0<" in html
    assert ">25.0<" in html


def test_detail_null_category_is_kept_under_vacio_bucket_not_dropped():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", None], "neto": [100.0, 50.0]})
    code = build_summary_detail_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "(vacío)" in result["result_html"]
    assert ">$ 50<" in result["result_html"]


def test_detail_zero_group_total_does_not_produce_inf_or_nan():
    """Same degenerate case already guarded elsewhere in this module: a
    group whose rows cancel out to exactly zero must not leak 'inf'/'nan'
    into the '% de su grupo' column."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "A"], "saldo": [1000.0, -1000.0]})
    code = build_summary_detail_code("df", ["cliente"], "saldo")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "inf" not in result["result_html"]
    assert "nan" not in result["result_html"]


def test_detail_multiple_columns_uses_composite_grouping_key():
    code = build_summary_detail_code("df", ["cliente", "mes"], "neto")
    _assert_valid_python(code)
    assert ".astype(str).agg(' - '.join, axis=1)" in code


def test_detail_includes_80_20_marker_column():
    """Bug report: checking "Mostrar detalle" silently dropped the 80/20
    Pareto analysis the user already had in the plain summary - the marker
    belongs on each group's TOTAL row (the group-level metric), not on the
    individual rows underneath it (which already have their own
    '% de su grupo')."""
    code = build_summary_detail_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "'80/20'" in code
    assert "_acum[_acum >= 80]" in code


def test_detail_prints_plain_language_pareto_insight():
    code = build_summary_detail_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "print(f'{_n_cruce} de {_n_total} {_palabra} el {_pct_cruce:.0f}% del total.')" in code


def test_detail_pareto_marker_lands_on_the_correct_group_total_row_not_an_individual_row():
    """Empirical verification (same standard as Story 8.3) - same A/B/C/D
    dataset already used to regression-test the aggregate summary's marker
    position (test_summary_pareto_runs_end_to_end_marks_the_right_row_and_prints_insight),
    now checking the marker lands on the group's "— TOTAL" row in the
    detailed view, not on one of its individual rows."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B", "C", "C", "C", "D"],
            "neto": [100.0, 100.0, 300.0, 200.0, 200.0, 100.0, 50.0],
        }
    )
    # totals: C=500 (47.6%), B=300 (28.6%), A=200 (19.0%), D=50 (4.8%) -> total=1050
    # sorted desc: C(cum 47.6), B(cum 76.2), A(cum 95.2), D(cum 100.0) -> crossing row is A
    code = build_summary_detail_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert html is not None
    assert html.count("✓ ← 80% aquí") == 1
    row_a_total = html[html.index("A — TOTAL") : html.index("</tr>", html.index("A — TOTAL"))]
    assert "✓ ← 80% aquí" in row_a_total

    stdout = result["stdout"]
    assert "3 de 4" in stdout
    assert "95% del total." in stdout


def test_detail_zero_total_does_not_produce_inf_or_nan_in_the_80_20_columns():
    """Same zero-total guard as build_summary_code, now also needed for the
    group-level '% del total'/'% acumulado'/'80/20' columns this detailed
    view carries on each TOTAL row."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "B"], "saldo": [1000.0, -1000.0]})
    code = build_summary_detail_code("df", ["cliente"], "saldo")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "inf" not in result["result_html"]
    assert "nan" not in result["result_html"]
    assert "inf" not in result["stdout"]


# --- Excel-style column filters (Story 8.4, user feedback: "colocar los
# filtros para ordenar también en ordenar tabla" / "también en Resumen y
# porcentaje por columna") -----------------------------------------------


def test_column_values_code_returns_sorted_distinct_values():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"vdor": ["C", "A", "B", "A", None]})
    code = build_column_values_code("df", "vdor")
    _assert_valid_python(code)
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["result_records"] == [{"vdor": "A"}, {"vdor": "B"}, {"vdor": "C"}]


def test_column_values_code_stringifies_numeric_values():
    """Filter comparison (_filter_lines) also uses .astype(str) - both sides
    must agree on the string form regardless of the column's real dtype."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"legal": [3, 6, 3]})
    code = build_column_values_code("df", "legal")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["result_records"] == [{"legal": "3"}, {"legal": "6"}]


def test_sort_with_filter_only_includes_selected_values():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"vdor": ["A", "B", "C"], "neto": [100.0, 200.0, 300.0]}
    )
    code = build_sort_code("df", "neto", False, filters=[{"column": "vdor", "values": ["A", "C"]}])
    _assert_valid_python(code)
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert ">A<" in html and ">C<" in html
    assert ">B<" not in html


def test_sort_filter_percentages_reflect_the_filtered_subset_not_the_whole_file():
    """Excel's own behavior when you filter+look at a %: the total is of
    what's VISIBLE, not the whole underlying file."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"vdor": ["A", "B", "C"], "cantidad": [100.0, 200.0, 300.0]}
    )
    # Filtered to just A and C (100 + 300 = 400 total) - A should be 25%, not
    # 100/(100+200+300)=16.7% (the unfiltered grand total).
    code = build_sort_code(
        "df", "cantidad", False, filters=[{"column": "vdor", "values": ["A", "C"]}]
    )
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "25.0" in result["result_html"]
    assert "16.7" not in result["result_html"]


def test_sort_without_filters_is_unaffected_by_the_filters_parameter():
    """filters=None (the default) must produce byte-identical code to before
    this feature existed - no regression for the common, filter-less case."""
    with_default = build_sort_code("df", "neto", False)
    with_empty_list = build_sort_code("df", "neto", False, filters=[])
    with_none = build_sort_code("df", "neto", False, filters=None)
    assert with_default == with_empty_list == with_none
    assert "_filtrado" not in with_default


def test_summary_with_filter_only_aggregates_selected_values():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B", "C"],
            "vdor": ["V1", "V1", "V2", "V1"],
            "neto": [100.0, 50.0, 200.0, 300.0],
        }
    )
    # Filtered to vdor=V1 only -> cliente A totals 150, C totals 300; B (V2) excluded entirely.
    code = build_summary_code(
        "df", ["cliente"], "neto", filters=[{"column": "vdor", "values": ["V1"]}]
    )
    _assert_valid_python(code)
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert ">B<" not in html
    assert ">A<" in html and ">C<" in html


def test_summary_detail_with_filter_excludes_non_matching_rows_and_groups():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B"],
            "legal": [3, 6, 3],
            "neto": [100.0, 50.0, 200.0],
        }
    )
    code = build_summary_detail_code(
        "df", ["cliente"], "neto", filters=[{"column": "legal", "values": ["3"]}]
    )
    _assert_valid_python(code)
    result = execute_code(code, namespace)
    assert result["error"] is None
    html = result["result_html"]
    assert "150.0" not in html  # A's un-filtered total (100+50) must not appear
    assert ">B<" in html


def test_filters_with_a_single_quote_in_the_value_do_not_break_generated_syntax():
    """Filter values, like column names, can come from real (messy)
    user-uploaded Excel content - repr() must be used to embed them."""
    code = build_sort_code(
        "df", "neto", False, filters=[{"column": "cliente", "values": ["O'Brien", "A"]}]
    )
    _assert_valid_python(code)


# --- Pareto diagram (bars + cumulative-% line), drawn automatically ------
# (user feedback: "esta grafica la tenemos que sacar al instante en que
# hacemos el Resumen y porcentaje por columna con sus ejes en porcentaje")


def test_summary_code_also_draws_a_pareto_chart():
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "_ax1.bar(" in code
    assert "_ax2 = _ax1.twinx()" in code
    assert "_ax2.plot(" in code
    assert "_ax2.axhline(80" in code
    # the table itself is still the cell's final expression - the chart must
    # not replace it
    assert code.strip().splitlines()[-1].startswith("pd.DataFrame(")


def test_summary_pareto_chart_runs_end_to_end_and_produces_an_image():
    """Empirical verification: execution.py's _capture_figure() must pick up
    the chart automatically (it runs after every cell regardless of the
    cell's final expression), so the SAME response carries both the table
    (result_html) and the chart (image_base64)."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["A", "A", "B", "C", "C", "C"],
            "neto": [100.0, 100.0, 300.0, 200.0, 200.0, 100.0],
        }
    )
    code = build_summary_code("df", ["cliente"], "neto")
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["result_html"] is not None
    assert result["image_base64"]


def test_summary_pareto_chart_hides_x_labels_past_the_cardinality_threshold():
    """A real file had 79 clients - individual x-axis labels for that many
    bars would only overlap into unreadable clutter, so they're hidden past
    HIGH_CARDINALITY_THRESHOLD (same one chart_builder.py uses)."""
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert f"if len(_t) <= {HIGH_CARDINALITY_THRESHOLD}:" in code
    assert "_ax1.set_xticks([])" in code


def test_summary_pareto_chart_formats_money_column_y_axis_as_colombian_pesos():
    code = build_summary_code("df", ["cliente"], "neto")
    _assert_valid_python(code)
    assert "'$ ' + f'{y:,.0f}'.replace(',', '.')" in code


def test_summary_pareto_chart_leaves_non_money_column_y_axis_unchanged():
    code = build_summary_code("df", ["cliente"], "cantidad")
    _assert_valid_python(code)
    assert "f'{y:,.0f}'" in code
    assert "$" not in code


# --- Pareto (80/20) also for "Ordenar tabla", at individual-ROW level -----
# (user feedback: "tengo entendido que deberia hacerse no con el acumulado
# por representante legal sino por el detallado")


def test_sort_descending_also_gets_the_80_20_marker_and_chart():
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert "'80/20'" in code
    assert "_ax1.bar(" in code
    assert "_ax2 = _ax1.twinx()" in code


def test_sort_ascending_does_not_get_the_80_20_marker_or_chart():
    """Ascending order ("menor a mayor") has no natural "80/20 from the top"
    reading - keeps the pre-existing %/cumulative-only view unchanged."""
    code = build_sort_code("df", "neto", True)
    _assert_valid_python(code)
    assert "'80/20'" not in code
    assert "_ax1.bar(" not in code


def test_sort_descending_pareto_marks_the_right_row_and_prints_row_level_insight():
    """Empirical verification: the 80/20 is computed over INDIVIDUAL ROWS
    (not grouped by any category), and the printed sentence says "fila(s)",
    not "categoría(s)"."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    # 4 individual invoice rows (same client repeated - the row-level 80/20
    # must not collapse them into one group, unlike build_summary_code).
    namespace["df"] = pd.DataFrame(
        {
            "cliente": ["LATIN", "LATIN", "LATIN", "OTRO"],
            "neto": [500.0, 290.0, 150.0, 60.0],
        }
    )
    code = build_sort_code("df", "neto", False)
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["result_html"] is not None
    assert result["image_base64"]
    # totals: 500+290+150+60=1000 -> cum 50, 79, 94, 100 - crossing at row 3 (94%)
    assert "3 de 4" in result["stdout"]
    assert "fila" in result["stdout"]
    assert "categoría" not in result["stdout"]


def test_sort_descending_pareto_formats_money_column_in_chart_y_axis():
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert "'$ ' + f'{y:,.0f}'.replace(',', '.')" in code


def test_sort_descending_pareto_zero_total_does_not_produce_inf_or_nan():
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame({"cliente": ["A", "B"], "saldo": [1000.0, -1000.0]})
    code = build_sort_code("df", "saldo", False)
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert "inf" not in result["result_html"]
    assert "nan" not in result["result_html"]
    assert "inf" not in result["stdout"]
