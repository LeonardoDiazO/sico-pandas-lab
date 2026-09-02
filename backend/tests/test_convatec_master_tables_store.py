import pandas as pd

from app.convatec import master_tables_store


def test_load_returns_none_tuple_when_nothing_persisted():
    assert master_tables_store.exists() is False
    assert master_tables_store.load() == (None, None, None)


def test_save_then_load_roundtrips_dataframes():
    producto = pd.DataFrame([{"SAP Code": "1", "ICC": "1"}])
    representantes = pd.DataFrame([{"Convenio": "X", "Representante": "Y"}])
    convenios = pd.DataFrame([{"CONVENIO": "X", "CIUDAD": "BOGOTA"}])

    master_tables_store.save(producto, representantes, convenios)

    assert master_tables_store.exists() is True
    loaded_producto, loaded_representantes, loaded_convenios = master_tables_store.load()
    pd.testing.assert_frame_equal(loaded_producto, producto)
    pd.testing.assert_frame_equal(loaded_representantes, representantes)
    pd.testing.assert_frame_equal(loaded_convenios, convenios)


def test_load_returns_none_tuple_when_persisted_files_are_unreadable(caplog):
    """A cache written by a different pandas/numpy version (or otherwise
    corrupted) must degrade to "nothing persisted" instead of raising -- this
    dict is loaded once, unconditionally, in create_app(), so an exception
    here used to take down the entire backend at startup, not just Convatec."""
    files = master_tables_store._files()
    master_tables_store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in files.values():
        path.write_bytes(b"not a valid pickle")

    assert master_tables_store.exists() is True  # files exist, just unreadable
    assert master_tables_store.load() == (None, None, None)


def test_save_overwrites_previous_persisted_version():
    first = pd.DataFrame([{"CONVENIO": "PRIMERO", "CIUDAD": "BOGOTA"}])
    second = pd.DataFrame([{"CONVENIO": "SEGUNDO", "CIUDAD": "MEDELLIN"}])
    other = pd.DataFrame([{"a": 1}])

    master_tables_store.save(other, other, first)
    master_tables_store.save(other, other, second)

    _, _, loaded_convenios = master_tables_store.load()
    pd.testing.assert_frame_equal(loaded_convenios, second)
