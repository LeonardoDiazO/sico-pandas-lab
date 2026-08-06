import pytest

from app.convatec import master_tables_store


@pytest.fixture(autouse=True)
def _isolate_convatec_master_tables_store(tmp_path, monkeypatch):
    """Every test gets its own throwaway directory for the persisted
    Convatec master tables -- otherwise test runs would read/write the real
    `backend/instance/convatec/` data seeded from Convatec's actual files."""
    monkeypatch.setattr(master_tables_store, "DATA_DIR", tmp_path / "convatec")
