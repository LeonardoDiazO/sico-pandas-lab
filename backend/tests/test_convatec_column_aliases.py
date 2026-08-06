import pandas as pd

from app.convatec.column_aliases import normalize_columns


def test_normalizes_accented_codigo_variant():
    df = pd.DataFrame([{"Código": "1004113", "Convenio": "X"}])
    result = normalize_columns(df)
    assert "Codigo" in result.columns
    assert "Código" not in result.columns


def test_does_not_overwrite_existing_canonical_column():
    df = pd.DataFrame([{"Codigo": "1", "Código": "2"}])
    result = normalize_columns(df)
    # canonical column already present -- the accented duplicate is left as-is
    # rather than silently overwriting real data with a merge collision.
    assert result["Codigo"].iloc[0] == "1"
    assert "Código" in result.columns


def test_leaves_unrelated_columns_untouched():
    df = pd.DataFrame([{"Convenio": "X", "Valor Total": 100.0}])
    result = normalize_columns(df)
    assert list(result.columns) == ["Convenio", "Valor Total"]
