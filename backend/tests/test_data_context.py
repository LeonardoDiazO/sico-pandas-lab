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
