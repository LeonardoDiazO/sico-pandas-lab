import ast

from app.notebook.table_builder import build_sort_code, build_summary_code


def _assert_valid_python(code):
    ast.parse(code)  # raises SyntaxError if the generated code is malformed


def test_sort_descending_by_default_shape():
    code = build_sort_code("df", "neto", False)
    _assert_valid_python(code)
    assert code == "df.sort_values('neto', ascending=False)"


def test_sort_ascending():
    code = build_sort_code("df", "neto", True)
    _assert_valid_python(code)
    assert code == "df.sort_values('neto', ascending=True)"


def test_column_name_with_a_single_quote_does_not_break_generated_syntax():
    """Column names come from user-uploaded Excel content - repr() must be
    used to embed them, not manual string concatenation (same security
    pattern already established by chart_builder.py)."""
    code = build_sort_code("df", "vendor's net", False)
    _assert_valid_python(code)


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
    # percentages, not just the 2 non-null rows (300.0)
    assert ">50.0<" in result["result_html"]


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
    # 3 groups x 3 numeric columns (neto, % del total, % acumulado) = 9 cells
    # (the 4th column, '80/20', is text/empty - Story 8.3 - and never
    # matches this digit-only pattern)
    assert len(percentages) == 9
    # "% acumulado" is the 3rd <td> in each row (neto, % del total, % acumulado, ...)
    row_c = html[html.index(">C<") : html.index("</tr>", html.index(">C<"))]
    cells_c = re.findall(r"<td[^>]*>([^<]*)</td>", row_c)
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
    assert html.count("← aquí se cruza el 80%") == 1

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
