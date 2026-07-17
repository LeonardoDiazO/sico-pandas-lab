import time

import pytest

from app.data_access import sico_client


@pytest.fixture(autouse=True)
def fake_table_cache(monkeypatch):
    """Pre-fill the table-name cache so tests never touch a real database."""
    monkeypatch.setitem(
        sico_client._TABLES_CACHE,
        "tables",
        ["02_movcabeza", "02_movimiento", "02_item", "02_itemprecios", "otra_tabla"],
    )
    monkeypatch.setitem(sico_client._TABLES_CACHE, "fetched_at", time.time())
    yield


@pytest.mark.parametrize(
    "name",
    ["temporal_armando", "temp_2799", "tem_admon", "pos_1014464245_1", "vista_saldo", "vist_cartera00", "v_facrelacion"],
)
def test_excluded_prefixes_are_filtered_out(name):
    assert sico_client._is_excluded(name)


@pytest.mark.parametrize("name", ["02_movimiento", "05_sueldos", "clientes", "usuarios"])
def test_business_tables_are_not_excluded(name):
    # These stay visible per the user's decision - only scratch/temp/pos/view
    # prefixes are filtered, not sensitive-but-real business tables.
    assert not sico_client._is_excluded(name)


def test_load_table_rejects_excluded_prefix_even_if_it_existed():
    with pytest.raises(ValueError):
        sico_client.load_table("temporal_armando")


def test_list_tables_returns_every_table_in_the_schema():
    names = [t["table"] for t in sico_client.list_tables()]
    # Not restricted to the original 4 - any table in the schema is listed.
    assert names == ["02_movcabeza", "02_movimiento", "02_item", "02_itemprecios", "otra_tabla"]
    assert all(t["schema"] == "sco" for t in sico_client.list_tables())


def test_load_table_rejects_unknown_table():
    with pytest.raises(ValueError):
        sico_client.load_table("no_existe_en_el_esquema")


def test_load_table_accepts_any_real_table_including_new_ones():
    # Should not raise for a table that only exists via dynamic discovery
    # (not part of the old hardcoded 4-table allowlist).
    sico_client._validate("otra_tabla")  # no exception


def test_select_only_guard_allows_select():
    assert sico_client.assert_select_only("SELECT * FROM `sco`.`02_item` LIMIT 5")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM `sco`.`02_item`",
        "UPDATE `sco`.`02_item` SET x=1",
        "INSERT INTO `sco`.`02_item` VALUES (1)",
        "DROP TABLE `sco`.`02_item`",
        "TRUNCATE `sco`.`02_item`",
        "SELECT 1; DELETE FROM `sco`.`02_item`",  # stacked statement
    ],
)
def test_select_only_guard_rejects_writes(sql):
    with pytest.raises(ValueError):
        sico_client.assert_select_only(sql)
