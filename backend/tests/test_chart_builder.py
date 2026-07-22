import ast

import pytest

from app.notebook.chart_builder import (
    HIGH_CARDINALITY_THRESHOLD,
    TOP_N_CATEGORIES_BEFORE_OTROS,
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
    assert "_ax.pie(" in code


def test_torta_without_value_column_counts_rows():
    code = build_chart_code("torta", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert "_ax.pie(" in code


def test_barras_with_value_column():
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert ".plot.bar(" in code


def test_barras_without_value_column():
    code = build_chart_code("barras", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert ".plot.bar(" in code


def test_linea_converts_date_column_without_fixed_format():
    code = build_chart_code("linea", "df", ["dia"], "neto")
    _assert_valid_python(code)
    assert "pd.to_datetime(" in code
    assert "errors='coerce'" in code
    assert "format=" not in code
    assert ".plot.line()" in code


def test_linea_casts_to_string_before_parsing_so_yyyymmdd_integers_work():
    """Bug found while visually reviewing generated charts: a 'fecha' column
    stored as a bare integer YYYYMMDD (e.g. 20260602 - the exact shape
    excel_profiler.py's own DATE_YYYYMMDD_PATTERN already recognizes and
    classifies as "fecha") gets misparsed by pd.to_datetime() when passed
    the raw int - pandas treats a bare number as nanoseconds-since-epoch,
    producing a garbage date near 1970 instead of 2026. Casting to str
    first (same pattern excel_profiler.py itself uses to detect these
    columns - astype(str) then parse) fixes it, and still coerces real
    garbage values to NaT same as before."""
    code = build_chart_code("linea", "df", ["dia"], "neto")
    _assert_valid_python(code)
    assert "pd.to_datetime(df['dia'].astype(str), errors='coerce')" in code

    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    namespace["df"] = pd.DataFrame(
        {"dia": [20260601, 20260602, 20260603], "neto": [100.0, 200.0, 150.0]}
    )
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["image_base64"]

    parsed = pd.to_datetime(namespace["df"]["dia"].astype(str), errors="coerce")
    assert parsed.dt.year.eq(2026).all()  # not ~1970, the pre-fix garbage result


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
    assert "_ax.pie(" in code


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
    assert ".plot.bar(" in code


def test_single_column_generated_code_is_byte_identical_to_pre_7_2():
    """Was pinned exactly for AC3 (Story 7.2) to guard the multi-column
    refactor's one-column path. Story 7.4 intentionally changed the torta
    code (figsize + top-N-plus-Otros wrapper); the Epic 7 code review then
    added `.groupby(level=0, sort=False).sum().clip(lower=0)`; post-Epic-7,
    TOP_N_CATEGORIES_BEFORE_OTROS was aligned with HIGH_CARDINALITY_THRESHOLD
    (see test_top_n_before_otros_matches_cardinality_warning_threshold); and
    the "professional look" pass (user feedback) replaced the bare
    `.plot.pie(...)` one-liner with an explicit `_ax.pie(...)` + side legend
    + `plt.subplots(figsize=(11, 8))` + bold title; a follow-up feedback
    round then added a per-slice percentage to every legend entry (see
    test_torta_legend_includes_percentage_for_every_slice) - this now pins
    that final string (using the live constant, not a bare literal, so this
    test doesn't silently go stale if the threshold moves again), still
    guarding that the underlying grouping expression
    (`df.groupby('vendedor')['neto'].sum().sort_values(...)`) is unchanged."""
    n = TOP_N_CATEGORIES_BEFORE_OTROS
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    assert code == (
        f"_chart_data = (lambda _s: _s if len(_s) <= {n} else "
        f"pd.concat([_s.iloc[:{n}], pd.Series({{'Otros': _s.iloc[{n}:].sum()}})]))"
        "(df.groupby('vendedor')['neto'].sum().sort_values(ascending=False))"
        ".groupby(level=0, sort=False).sum().clip(lower=0)\n"
        "_fig, _ax = plt.subplots(figsize=(11, 8))\n"
        "_wedges, _texts, _autotexts = _ax.pie(_chart_data.values, labels=None, "
        "autopct=lambda p: f'{p:.1f}%' if p >= 3 else '', "
        "colors=plt.get_cmap('tab20').colors[:len(_chart_data)], pctdistance=0.8)\n"
        "_total = _chart_data.sum()\n"
        "_ax.legend(_wedges, "
        "[f'{name} - {val / _total * 100:.1f}%' for name, val in _chart_data.items()], "
        "loc='center left', bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)\n"
        "plt.title('neto por vendedor', fontsize=13, fontweight='bold')\n"
        "plt.tight_layout()"
    )


def test_top_n_before_otros_matches_cardinality_warning_threshold():
    """Design decision (post-Epic-7, user feedback): "Otros" bucketing must
    only kick in once the user has already seen and dismissed the
    cardinality warning (Story 5.4) by clicking "Generar de todos modos" -
    below HIGH_CARDINALITY_THRESHOLD, every category should render
    individually, closing what used to be a silent 9-{old value} zone where
    the chart bucketed categories the user was never warned about."""
    assert TOP_N_CATEGORIES_BEFORE_OTROS == HIGH_CARDINALITY_THRESHOLD


# --- Story 7.4: torta legibility (figsize + top-N-plus-Otros) ------------------


def test_torta_always_has_a_larger_figsize():
    code = build_chart_code("torta", "df", ["vendedor"], None)
    _assert_valid_python(code)
    assert "figsize=(11, 8)" in code


def test_torta_generated_code_includes_otros_bucketing_logic():
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "'Otros'" in code
    assert f"len(_s) <= {TOP_N_CATEGORIES_BEFORE_OTROS}" in code


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
    assert f"len(_s) <= {TOP_N_CATEGORIES_BEFORE_OTROS}" in code


def test_barras_gets_its_own_figsize_but_never_negative_value_clip():
    """barras now gets its own figsize too (professional-look pass, user
    feedback) - distinct from torta's (11, 8), which needs the extra width
    for the side legend; barras doesn't have a legend, so (10, 7) is enough
    room for rotated x-axis labels. clip(lower=0) still stays torta-only:
    it exists only because a pie slice can't be negative (Epic 7 code
    review); a bar chart can meaningfully show a negative group total."""
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "figsize=(10, 7)" in code
    assert "clip(lower=0)" not in code


# --- Professional-look pass (user feedback): palette, legends, axis format ----


def test_torta_uses_side_legend_instead_of_on_slice_labels():
    """Up to TOP_N_CATEGORIES_BEFORE_OTROS+1 long composite labels (Story
    7.2) directly on pie slices overlap into an unreadable stack - they move
    to a side legend instead."""
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "labels=None" in code
    assert "_ax.legend(" in code


def test_torta_legend_includes_percentage_for_every_slice():
    """User feedback: on-slice autopct only shows a percentage for slices
    >=3% (to avoid clutter) - small slices' percentages were invisible
    anywhere. Every legend entry must carry its own percentage instead
    (guaranteed legible regardless of slice count, unlike leader-line
    labels around the pie which can still collide with enough categories)."""
    code = build_chart_code("torta", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "_total = _chart_data.sum()" in code
    assert "for name, val in _chart_data.items()" in code
    assert "val / _total * 100" in code

    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    namespace = build_namespace()
    # A long tail of small slices past the top categories - exactly the
    # shape where the old on-slice-only percentages went invisible.
    namespace["df"] = pd.DataFrame(
        {
            "vendedor": [f"V{i}" for i in range(30)],
            "neto": [1000] + [1] * 29,  # one dominant slice, 29 tiny ones
        }
    )
    result = execute_code(code, namespace)
    assert result["error"] is None
    assert result["image_base64"]


def test_torta_and_barras_use_a_qualitative_color_palette():
    for chart_type in ("torta", "barras"):
        code = build_chart_code(chart_type, "df", ["vendedor"], "neto")
        _assert_valid_python(code)
        assert "plt.get_cmap('tab20')" in code


def test_barras_formats_y_axis_without_scientific_notation():
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "FuncFormatter" in code


def test_barras_truncates_long_x_axis_labels():
    code = build_chart_code("barras", "df", ["vendedor"], "neto")
    _assert_valid_python(code)
    assert "set_xticklabels(" in code
    assert "[:28]" in code


def test_every_generated_code_has_a_bold_title():
    for chart_type, columns, value_column in [
        ("torta", ["vendedor"], "neto"),
        ("barras", ["vendedor"], None),
        ("linea", ["dia"], "neto"),
        ("histograma", [], "neto"),
    ]:
        code = build_chart_code(chart_type, "df", columns, value_column)
        _assert_valid_python(code)
        assert "fontweight='bold'" in code


def test_professional_look_torta_and_barras_run_end_to_end_without_error():
    """String assertions above check the generated code contains the right
    calls - this executes it for real against a synthetic DataFrame (same
    empirical-verification standard as the Epic 7 review's runtime-safety
    tests) to catch anything only a real matplotlib/pandas call would
    surface (a typo in a kwarg name, an incompatible argument combination)."""
    import matplotlib

    matplotlib.use("Agg")
    import pandas as pd

    from app.notebook.execution import build_namespace, execute_code

    df = pd.DataFrame(
        {
            "vendedor": [f"V{i}" for i in range(20)] * 3,
            "neto": [100 - i for i in range(20)] * 3,
        }
    )
    for chart_type in ("torta", "barras"):
        namespace = build_namespace()
        namespace["df"] = df
        code = build_chart_code(chart_type, "df", ["vendedor"], "neto")
        result = execute_code(code, namespace)
        assert result["error"] is None
        assert result["image_base64"]


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
