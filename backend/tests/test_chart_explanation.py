from app.notebook.chart_explanation import build_chart_explanation

_TECH_JARGON = ["df.", "groupby", "value_counts", "plt.", ".sum()", "['", "lambda"]


def _assert_plain_language(text):
    assert text
    for jargon in _TECH_JARGON:
        assert jargon not in text


def test_torta_with_value_column_mentions_both():
    text = build_chart_explanation("torta", ["vendedor"], "neto")
    _assert_plain_language(text)
    assert "vendedor" in text
    assert "neto" in text


def test_torta_without_value_column_mentions_column_only():
    text = build_chart_explanation("torta", ["vendedor"], None)
    _assert_plain_language(text)
    assert "vendedor" in text


def test_barras_with_value_column_mentions_both():
    text = build_chart_explanation("barras", ["vendedor"], "neto")
    _assert_plain_language(text)
    assert "vendedor" in text
    assert "neto" in text


def test_barras_without_value_column_mentions_column_only():
    text = build_chart_explanation("barras", ["vendedor"], None)
    _assert_plain_language(text)
    assert "vendedor" in text


def test_multiple_columns_are_joined_with_y():
    text = build_chart_explanation("barras", ["vendedor", "mes"], "neto")
    _assert_plain_language(text)
    assert "vendedor" in text
    assert "mes" in text
    assert " y " in text


def test_linea_with_value_column_mentions_date_and_value():
    text = build_chart_explanation("linea", ["dia"], "neto")
    _assert_plain_language(text)
    assert "dia" in text
    assert "neto" in text


def test_linea_without_value_column_mentions_date_only():
    text = build_chart_explanation("linea", ["dia"], None)
    _assert_plain_language(text)
    assert "dia" in text


def test_histograma_mentions_value_column():
    text = build_chart_explanation("histograma", [], "neto")
    _assert_plain_language(text)
    assert "neto" in text


def test_unknown_chart_type_returns_none():
    assert build_chart_explanation("scatter", ["vendedor"], None) is None


# --- "Otros" bucketing caveat: torta (Story 7.4) + barras (post-Epic-7) ---


def test_torta_mentions_otros_bucketing_caveat():
    """chart_builder.py's torta code (Story 7.4) folds everything past the
    top TOP_N_CATEGORIES_BEFORE_OTROS categories into a single "Otros"
    slice - the explanation must say so (a static fact about torta, always
    true, doesn't require knowing the actual category count - same
    "closed-set inputs only" principle the module already follows)."""
    text = build_chart_explanation("torta", ["vendedor"], "neto")
    _assert_plain_language(text)
    assert "Otros" in text


def test_barras_also_mentions_otros_bucketing_caveat():
    """Real usage after Epic 7 shipped showed multi-column combinations
    (Story 7.2) routinely exceed the cardinality threshold, and 80+ raw bars
    is just as illegible as 80+ pie slices - chart_builder.py now applies
    the same "Otros" bucketing to barras, so the explanation must mention it
    here too, not just for torta."""
    text = build_chart_explanation("barras", ["vendedor"], "neto")
    _assert_plain_language(text)
    assert "Otros" in text
