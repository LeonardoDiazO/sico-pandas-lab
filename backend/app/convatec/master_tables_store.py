"""Persists the uploaded master tables (PRODUCTO, REPRESENTANTES, CONVENIOS)
to local disk so they survive a backend restart -- request 2026-08-06: "que
tengamos todo a la mano" without re-uploading the maestro workbook every
session. Lives under `backend/instance/`, already covered by .gitignore
(Flask's own convention for local-only data) -- this is Convatec's real
commercial structure (which rep covers which territory), not something to
ever check into version control.

This is the one persistence point for this demo iteration (PRD S5.3 covers
the rest: uploaded sales cycles and results still live in memory only).
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Module-level so tests can monkeypatch it to a tmp_path and never touch
# the real persisted Convatec data (or leak fixture data into it).
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "instance" / "convatec"


def _files():
    return {
        "producto": DATA_DIR / "producto.pkl",
        "representantes": DATA_DIR / "representantes.pkl",
        "convenios": DATA_DIR / "convenios.pkl",
    }


def save(producto_table: pd.DataFrame, representantes_table: pd.DataFrame, convenios_table: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = _files()
    producto_table.to_pickle(files["producto"])
    representantes_table.to_pickle(files["representantes"])
    convenios_table.to_pickle(files["convenios"])


def load():
    """Returns (producto, representantes, convenios), or (None, None, None)
    if nothing has ever been persisted -- or if what's on disk can't be read
    back (e.g. a pickle written by a different pandas/numpy version than the
    one now installed). A stale/incompatible cache must never take down app
    startup for every module: treat it the same as "nothing persisted yet"
    and let the user re-upload the maestros workbook to refresh it."""
    files = _files()
    if not all(path.exists() for path in files.values()):
        return None, None, None
    try:
        return (
            pd.read_pickle(files["producto"]),
            pd.read_pickle(files["representantes"]),
            pd.read_pickle(files["convenios"]),
        )
    except Exception:
        logger.warning(
            "No se pudo leer el caché de maestros de Convatec en %s -- se ignora "
            "y se trata como si no hubiera maestros cargados. Vuelve a subir el "
            "Excel de maestros para regenerarlo.",
            DATA_DIR,
            exc_info=True,
        )
        return None, None, None


def exists() -> bool:
    return all(path.exists() for path in _files().values())
