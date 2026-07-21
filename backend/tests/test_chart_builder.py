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
    code = build_chart_code("torta", "df", "vendedor", "neto")
    _assert_valid_python(code)
    assert "groupby('vendedor')" in code
    assert "['neto']" in code
    assert ".sum()" in code
    assert ".plot.pie(" in code


def test_torta_without_value_column_counts_rows():
    code = build_chart_code("torta", "df", "vendedor", None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert ".plot.pie(" in code


def test_barras_with_value_column():
    code = build_chart_code("barras", "df", "vendedor", "neto")
    _assert_valid_python(code)
    assert ".plot.bar()" in code


def test_barras_without_value_column():
    code = build_chart_code("barras", "df", "vendedor", None)
    _assert_valid_python(code)
    assert "value_counts()" in code
    assert ".plot.bar()" in code


def test_linea_converts_date_column_without_fixed_format():
    code = build_chart_code("linea", "df", "dia", "neto")
    _assert_valid_python(code)
    assert "pd.to_datetime(" in code
    assert "errors='coerce'" in code
    assert "format=" not in code
    assert ".plot.line()" in code


def test_histograma_ignores_grouping_column_uses_only_value_column():
    code = build_chart_code("histograma", "df", "vendedor", "neto")
    _assert_valid_python(code)
    assert "'vendedor'" not in code
    assert "['neto']" in code
    assert ".plot.hist()" in code


def test_column_names_with_a_single_quote_do_not_break_generated_syntax():
    """Column names come from user-uploaded Excel content - repr() must be
    used to embed them, not manual string concatenation."""
    code = build_chart_code("torta", "df", "vendor's code", "amount")
    _assert_valid_python(code)


def test_unknown_chart_type_raises_value_error():
    with pytest.raises(ValueError):
        build_chart_code("scatter", "df", "vendedor", None)


def test_every_generated_code_sets_a_title():
    for chart_type, column, value_column in [
        ("torta", "vendedor", "neto"),
        ("barras", "vendedor", None),
        ("linea", "dia", "neto"),
        ("histograma", None, "neto"),
    ]:
        code = build_chart_code(chart_type, "df", column, value_column)
        assert "plt.title(" in code


def test_needs_cardinality_check_only_for_torta_and_barras():
    assert needs_cardinality_check("torta") is True
    assert needs_cardinality_check("barras") is True
    assert needs_cardinality_check("linea") is False
    assert needs_cardinality_check("histograma") is False


def test_cardinality_check_code_is_valid_and_safe():
    code = build_cardinality_check_code("df", "vendedor")
    ast.parse(code)
    assert "nunique()" in code
    assert "'vendedor'" in code

    unsafe_code = build_cardinality_check_code("df", "vendor's code")
    ast.parse(unsafe_code)
