from app.guided import data_context


def _profile(variable, columns):
    return {"variable": variable, "columns": columns}


def test_returns_none_when_no_profile_is_known():
    assert data_context.resolve_context("01-fundamentos", None) is None


def test_returns_none_for_a_lesson_out_of_scope():
    profile = _profile("df", [{"name": "Vendedor", "type": "categorica"}, {"name": "Neto", "type": "numerica"}])
    assert data_context.resolve_context("02-filtrar-ordenar", profile) is None
    assert data_context.resolve_context("04-combinar-tablas", profile) is None


def test_resolves_a_full_profile_for_fundamentos():
    profile = _profile(
        "df",
        [
            {"name": "Vendedor", "type": "categorica"},
            {"name": "Cantidad", "type": "numerica"},
            {"name": "Neto", "type": "numerica"},
        ],
    )
    context = data_context.resolve_context("01-fundamentos", profile)
    assert context == {
        "table_var": "df",
        "roles": {"cat": "Vendedor", "num1": "Cantidad", "num2": "Neto"},
    }


def test_returns_none_when_only_one_numeric_column_exists_but_two_are_needed():
    """01-fundamentos and 03-agrupar both embed num1 AND num2 in the SAME
    synthetic dict literal (mov_cantidad + mov_neto in one pd.DataFrame(...))
    -- reusing one real column for both would substitute two different dict
    keys with the same name, silently dropping one value. Must fall back to
    the static example instead of generating that."""
    profile = _profile(
        "df",
        [{"name": "Ciudad", "type": "categorica"}, {"name": "Neto", "type": "numerica"}],
    )
    assert data_context.resolve_context("03-agrupar", profile) is None
    assert data_context.resolve_context("01-fundamentos", profile) is None


def test_resolves_distinct_columns_for_num1_and_num2_when_both_are_available():
    profile = _profile(
        "df",
        [
            {"name": "Ciudad", "type": "categorica"},
            {"name": "Cantidad", "type": "numerica"},
            {"name": "Neto", "type": "numerica"},
        ],
    )
    context = data_context.resolve_context("03-agrupar", profile)
    assert context["roles"]["num1"] == "Cantidad"
    assert context["roles"]["num2"] == "Neto"


def test_single_numeric_role_lesson_does_not_require_a_second_column():
    profile = _profile(
        "df",
        [{"name": "Vendedor", "type": "categorica"}, {"name": "Neto", "type": "numerica"}],
    )
    context = data_context.resolve_context("05-graficas", profile)
    assert context["roles"]["num1"] == "Neto"


def test_returns_none_when_missing_a_required_categorical_column():
    profile = _profile("df", [{"name": "Neto", "type": "numerica"}])
    assert data_context.resolve_context("01-fundamentos", profile) is None


def test_returns_none_when_missing_a_required_numeric_column():
    profile = _profile("df", [{"name": "Vendedor", "type": "categorica"}])
    assert data_context.resolve_context("05-graficas", profile) is None


def test_prefers_the_lowest_cardinality_categorical_column_over_file_order():
    """Real bug found in production: with several categorical columns
    available, picking the first one in FILE order landed on a ~200-value
    provider code instead of a 6-value salesperson column sitting right
    next to it - a confusing first "group by this" example (the printed
    insight read "47 de 210 categorías concentran..." instead of an actual
    takeaway like "2 de 6..."). "ProveedorCodigo" appears first in the
    profile's column order here on purpose, to prove selection follows
    uniqueRatio, not position."""
    profile = _profile(
        "df",
        [
            {"name": "ProveedorCodigo", "type": "categorica", "uniqueRatio": 0.95},
            {"name": "Vdor", "type": "categorica", "uniqueRatio": 0.03},
            {"name": "Neto", "type": "numerica", "uniqueRatio": 0.9},
        ],
    )
    context = data_context.resolve_context("05-graficas", profile)
    assert context["roles"]["cat"] == "Vdor"


def test_skips_a_degenerate_always_same_value_categorical_column():
    """Real bug found live right after the fix above: a sales report had
    several "Devolucion" (return) columns that are "0" on every single row
    - a single distinct value gives them the LOWEST possible uniqueRatio of
    all, so the ascending sort picked one of those over "Vdor" (a genuinely
    useful 6-value salesperson column), which is even less useful than the
    original file-order bug it was meant to fix."""
    profile = _profile(
        "df",
        [
            {
                "name": "Cantidad Devolucion",
                "type": "categorica",
                "uniqueRatio": 0.0016,
                "sampleValues": ["0"],
            },
            {"name": "Vdor", "type": "categorica", "uniqueRatio": 0.0099, "sampleValues": ["V 21", "V 41", "V 42"]},
            {"name": "Neto", "type": "numerica", "uniqueRatio": 0.9},
        ],
    )
    context = data_context.resolve_context("05-graficas", profile)
    assert context["roles"]["cat"] == "Vdor"


def test_categorical_column_missing_unique_ratio_sorts_last_not_crashes():
    """A profile from before excel_profiler.py started computing per-column
    stats (or any caller that omits it) must degrade safely - missing
    uniqueRatio is treated as the worst case (sorts last), never a KeyError."""
    profile = _profile(
        "df",
        [
            {"name": "SinStats", "type": "categorica"},  # no uniqueRatio key at all
            {"name": "Vdor", "type": "categorica", "uniqueRatio": 0.03},
            {"name": "Neto", "type": "numerica", "uniqueRatio": 0.9},
        ],
    )
    context = data_context.resolve_context("05-graficas", profile)
    assert context["roles"]["cat"] == "Vdor"


def test_substitute_identifiers_replaces_table_and_column_names_as_whole_words():
    context = {"table_var": "df", "roles": {"cat": "Vendedor", "num1": "Cantidad", "num2": "Neto"}}
    text = "df_02_movimiento.groupby('mov_item')['mov_neto'].sum()  # mov_cantidad no aplica aquí"
    result = data_context.substitute_identifiers(text, "01-fundamentos", context)
    assert result == "df.groupby('Vendedor')['Neto'].sum()  # Cantidad no aplica aquí"


def test_substitute_identifiers_does_not_touch_partial_matches():
    context = {"table_var": "df", "roles": {"cat": "mov_item_categoria", "num1": "Cantidad", "num2": "Neto"}}
    # "mov_item" must not clobber "mov_item_extendido" elsewhere in the text.
    text = "mov_item_extendido sigue igual, pero mov_item sí cambia"
    result = data_context.substitute_identifiers(text, "01-fundamentos", context)
    assert result == "mov_item_extendido sigue igual, pero mov_item_categoria sí cambia"
