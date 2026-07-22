import ast

import pytest

from app.notebook.chart_builder import (
    build_cardinality_check_code,
    build_chart_code,
    needs_cardinality_check,
)


def _assert_valid_python(code):
    ast.parse(code)  # raises SyntaxError if the generated code is malformed


def test_torta_with_value_column_groups_and_sums():
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "groupby('vendedor')" in code
    assert "['neto']" in code
    assert ".sum()" in code
    assert ".plot.pie(" in code


def test_torta_without_value_column_counts_rows():
    code = build_chart_code("torta", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert ".plot.pie(" in code


def test_barras_with_value_column():
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert ".plot.bar()" in code


def test_barras_without_value_column():
    code = build_chart_code("barras", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert ".plot.bar()" in code


def test_linea_converts_date_column_without_fixed_format():
    code = build_chart_code("linea", "df", ["dia"], "neto")
    _assert_valid_python(code)
    assert "pd.to_datetime(" in code
    assert "errors='coerce'" in code
    assert "format=" not in code
    assert ".plot.line()" in code


def test_histograma_ignores_grouping_column_uses_only_value_column():
    code = build_chart_code("histograma", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "'vendedor'" not in code
    assert "['neto']" in code
    assert ".plot.hist()" in code


def test_column_names_with_a_single_quote_do_not_break_generated_syntax():
    """Column names come from user-uploaded Excel content - repr() must be
    used to embed them, not manual string concatenation."""
    code = build_chart_code("torta", "df", ["vendor's code"], "amount")
    _assert_valid_python(code)


def test_unknown_chart_type_raises_value_error():
    with pytest.raises(ValueError):
        build_chart_code("scatter", "df", ["vendedor"], None)


def test_every_generated_code_sets_a_title():
    for chart_type, columns, value_column in [
        ("torta", ["vendedor"], "neto"),
        ("barras", ["vendedor"], None),
        ("linea", ["dia"], "neto"),
        ("histograma", [], "neto"),
    ]:
        code = build_chart_code(chart_type, "df", columns, value_column)
        assert "plt.title(" in code


def test_needs_cardinality_check_only_for_torta_and_barras():
    assert needs_cardinality_check("torta") is True
    assert needs_cardinality_check("barras") is True
    assert needs_cardinality_check("linea") is False
    assert needs_cardinality_check("histograma") is False


def test_cardinality_check_code_is_valid_and_safe():
    code = build_cardinality_check_code("df", ["vendedor"])
    ast.parse(code)
    assert "nunique()" in code
    assert "'vendedor'" in code

    unsafe_code = build_cardinality_check_code("df", ["vendor's code"])
    ast.parse(unsafe_code)


# --- Story 7.2: multiple columns -----------------------------------------------


def test_single_column_cardinality_check_is_unchanged():
    """AC3 - the one-column path must be byte-identical to the pre-7.2
    behavior, so the check above (with a 1-element list) still holds; this
    test pins the exact generated string as an extra guardrail."""
    code = build_cardinality_check_code("df", ["vendedor"])
    assert code == "df['vendedor'].nunique()"


def test_cardinality_check_with_multiple_columns_counts_unique_combinations():
    code = build_cardinality_check_code("df", ["vendedor", "mes"])
    _assert_valid_python(code)
    assert "drop_duplicates()" in code
    assert "['vendedor', 'mes']" in code
    assert "nunique()" not in code


def test_torta_with_two_categorical_columns_builds_composite_grouping_key():
    code = build_chart_code("torta", "df", ["vendedor", "mes"], None)
    _assert_valid_python(code)
    assert "['vendedor', 'mes']" in code
    assert ".astype(str).agg(' - '.join, axis=1)" in code
    assert "value_counts()" in code
    assert ".plot.pie(" in code


def test_multi_column_grouping_key_fills_missing_values_instead_of_literal_nan():
    """Epic 7 code review regression: a row with a null value in one of
    several grouping columns must not surface as the literal substring
    'nan' in the composite label (astype(str) on a NaN produces exactly
    that) - fillna() first so it reads as a real placeholder instead."""
    code = build_chart_code("torta", "df", ["vendedor", "sede"], None)
    _assert_valid_python(code)
    assert "fillna(" in code
    assert code.index("fillna(") < code.index(".astype(str)")


def test_barras_with_multiple_columns_and_value_column_groups_by_combination():
    code = build_chart_code("barras", "df", ["vendedor", "mes"], "neto")
    _assert_valid_python(code)
    assert ".astype(str).agg(' - '.join, axis=1)" in code
    assert "groupby(" in code
    assert "['neto']" in code
    assert ".sum()" in code
    assert ".plot.bar()" in code


def test_single_column_generated_code_is_byte_identical_to_pre_7_2():
    """Was pinned exactly for AC3 (Story 7.2) to guard the multi-column
    refactor's one-column path. Story 7.4 intentionally changed the torta
    code (figsize + top-N-plus-Otros wrapper); the Epic 7 code review then
    added `.groupby(level=0, sort=False).sum().clip(lower=0)` (see
    test_torta_merges_duplicate_otros_label and
    test_torta_clips_negative_values_before_plotting below) - this now pins
    that final string, still guarding that the underlying grouping
    expression (`df.groupby('vendedor')['neto'].sum().sort_values(...)`) is
    unchanged."""
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    assert code == (
        "(lambda _s: _s if len(_s) <= 8 else "
        "pd.concat([_s.iloc[:8], pd.Series({'Otros': _s.iloc[8:].sum()})]))"
        "(df.groupby('vendedor')['neto'].sum().sort_values(ascending=False))"
        ".groupby(level=0, sort=False).sum().clip(lower=0)"
        ".plot.pie(autopct='%1.1f%%', ylabel='', figsize=(8, 8))\n"
        "plt.title('neto por vendedor')\n"
        "plt.tight_layout()"
    )


# --- Story 7.4: torta legibility (figsize + top-N-plus-Otros) ------------------


def test_torta_always_has_a_larger_figsize():
    code = build_chart_code("torta", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "figsize=(8, 8)" in code


def test_torta_generated_code_includes_otros_bucketing_logic():
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "'Otros'" in code
    assert "len(_s) <= 8" in code


def test_torta_with_multiple_columns_still_wraps_the_composite_expression():
    code = build_chart_code("torta", "df", ["vendedor", "mes"], None)
    _assert_valid_python(code)
    assert "'Otros'" in code
    assert ".astype(str).agg(' - '.join, axis=1)" in code


# --- Post-Epic-7 refinement: "Otros" bucketing extended to barras -------------
#
# Real usage after Epic 7 shipped showed multi-column combinations (Story 7.2)
# routinely blow past HIGH_CARDINALITY_THRESHOLD (e.g. 3 columns -> 88 unique
# combinations) - Story 7.4 originally scoped "top-N + Otros" to torta only,
# on the assumption bars "scale reasonably" with more categories. 88 raw bars
# is not reasonable, so the same bucketing now applies to both chart types;
# only figsize and the negative-value clip (pie-specific - a bar CAN show a
# meaningful negative value, a pie slice can't) stay torta-only.


def test_barras_gets_otros_bucketing_too():
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "'Otros'" in code
    assert "len(_s) <= 8" in code


def test_barras_never_gets_figsize_or_negative_value_clip():
    """figsize is torta's "amontonada" fix specifically (AC1, Story 7.4) -
    barras never needed it. clip(lower=0) exists only because a pie slice
    can't be negative (Epic 7 code review); a bar chart can meaningfully
    show a negative group total, so barras must never floor it."""
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "figsize" not in code
    assert "clip(lower=0)" not in code


def test_barras_merges_duplicate_otros_label_too():
    code = build_chart_code("barras", "df", ["tipo_cliente"], None)
    _assert_valid_python(code)
    assert "groupby(level=0, sort=False).sum()" in code


# --- Epic 7 code review: torta runtime-safety fixes -----------------------


def test_torta_merges_duplicate_otros_label():
    """A real category can itself be named 'Otros' (e.g. a 'tipo_cliente'
    column). Without merging, pd.concat produces two index entries both
    labeled 'Otros' - two same-labeled wedges instead of one. The generated
    code must fold duplicate labels together (Series.groupby(level=0).sum())
    rather than rely on pd.concat to merge them (it doesn't)."""
    code = build_chart_code("torta", "df", ["tipo_cliente"], None)
    _assert_valid_python(code)
    assert "groupby(level=0, sort=False).sum()" in code

    import pandas as pd

    s = pd.Series({"Otros": 500, "v0": 100, "v1": 90, "v2": 80, "v3": 70, "v4": 60, "v5": 50, "v6": 40, "v7": 30})
    top_n = 8
    result = (
        (s if len(s) <= top_n else pd.concat([s.iloc[:top_n], pd.Series({"Otros": s.iloc[top_n:].sum()})]))
        .groupby(level=0, sort=False)
        .sum()
    )
    assert result.index.tolist().count("Otros") == 1
    assert result["Otros"] == 500 + 30  # real 'Otros' row + folded tail (v7 falls past top 8)


def test_torta_clips_negative_values_before_plotting():
    """A signed value_column (e.g. 'neto' with returns/refunds) can make the
    tail sum negative even when no individual group is negative on its own -
    matplotlib's pie() raises ValueError on any negative wedge size. The
    generated code must clip to zero before plotting rather than crash."""
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert ".clip(lower=0)" in code

    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    s = pd.Series(
        {"v0": 100, "v1": 90, "v2": 80, "v3": 70, "v4": 60, "v5": 50, "v6": 40, "v7": 30, "v8": 5, "v9": -60}
    ).sort_values(ascending=False)
    top_n = 8
    result = (
        (s if len(s) <= top_n else pd.concat([s.iloc[:top_n], pd.Series({"Otros": s.iloc[top_n:].sum()})]))
        .groupby(level=0, sort=False)
        .sum()
        .clip(lower=0)
    )
    assert result["Otros"] == 0  # 5 + (-60) = -55, clipped to 0 instead of crashing
    result.plot.pie(autopct="%1.1f%%", ylabel="", figsize=(8, 8))  # must not raise
