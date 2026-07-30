from app.notebook.table_explanation import (
    build_sort_explanation,
    build_summary_detail_explanation,
    build_summary_explanation,
)

_TECH_JARGON = ["df.", "groupby", "cumsum", "assign", ".sort_values", "lambda"]


def _assert_plain_language(text):
    assert text
    for jargon in _TECH_JARGON:
        assert jargon not in text


def test_sort_explanation_mentions_value_column_and_both_percentage_columns():
    text = build_sort_explanation("neto")
    _assert_plain_language(text)
    assert "neto" in text
    assert "% del total" in text
    assert "% acumulado" in text


def test_summary_explanation_mentions_grouping_column_and_value_column():
    text = build_summary_explanation(["cliente"], "neto")
    _assert_plain_language(text)
    assert "cliente" in text
    assert "neto" in text
    assert "% del total" in text
    assert "% acumulado" in text


def test_summary_explanation_joins_multiple_grouping_columns_with_y():
    text = build_summary_explanation(["cliente", "mes"], "neto")
    _assert_plain_language(text)
    assert "cliente" in text
    assert "mes" in text
    assert " y " in text


def test_summary_detail_explanation_mentions_grouping_column_value_column_and_its_own_percentage():
    text = build_summary_detail_explanation(["cliente"], "neto")
    _assert_plain_language(text)
    assert "cliente" in text
    assert "neto" in text
    assert "% de su grupo" in text
