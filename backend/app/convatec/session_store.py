"""Storage for uploaded files and the last processed result.

Master tables (PRODUCTO, REPRESENTANTES, CONVENIOS) are GLOBAL, not
per-session -- there is one Convatec, one canonical set of maestros; it
never made sense for two browser sessions to see different territory rules.
They are also persisted to disk (see `master_tables_store`) so a backend
restart doesn't require re-uploading the workbook -- request 2026-08-06.

Ventas (productos/servicios/envios) and the processed resultado stay
per-session -- those are one user's in-progress cycle, deliberately not
shared. Session id lifetime is whatever `SessionService` on the frontend
gives it (currently a `localStorage` value -- shared across every tab of the
same browser profile, not per-tab; matches the rest of sico-pandas-lab
today, see `frontend/src/app/core/session.service.ts`).

PRD S5.3 `[ASSUMPTION]`: ventas/resultado do NOT survive a process restart --
only the master tables do, by explicit request. Every public method takes
the lock for its entire read-modify-write, not just the initial
`setdefault` -- an earlier version only locked the dictionary lookup and
mutated the session's own dict afterwards unlocked, which two concurrent
requests for the same session id could race (found in code review).
"""
import threading

from app.convatec import master_tables_store


class ConvatecSessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}
        producto, representantes, convenios = master_tables_store.load()
        self._producto_table = producto
        self._representantes_table = representantes
        self._convenios_table = convenios

    def _get_or_create(self, session_id: str) -> dict:
        return self._sessions.setdefault(
            session_id,
            {
                "ventas": {},  # {"productos" | "servicios" | "envios_nacionales": DataFrame}
                "resultado": None,
                "reconocimiento_total": None,  # step 10: SAP vs Hyperion total check
            },
        )

    def set_master_tables(self, session_id: str, producto_table, representantes_table, convenios_table) -> None:
        """FR-3: a fresh upload replaces the whole previous set, no partial
        merge -- and for every session, not just the uploader's, since
        maestros are global. Persisted to disk immediately."""
        with self._lock:
            self._producto_table = producto_table
            self._representantes_table = representantes_table
            self._convenios_table = convenios_table
            master_tables_store.save(producto_table, representantes_table, convenios_table)

    def has_master_tables(self, session_id: str) -> bool:
        with self._lock:
            return self._producto_table is not None

    def set_ventas(self, session_id: str, tipo: str, df) -> None:
        with self._lock:
            self._get_or_create(session_id)["ventas"][tipo] = df

    def get_ventas(self, session_id: str, tipo: str):
        with self._lock:
            return self._get_or_create(session_id)["ventas"].get(tipo)

    def master_tables(self, session_id: str):
        """Returns (producto_table, representantes_table, convenios_table),
        or (None, None, None) if nothing has ever been uploaded/persisted --
        callers should check `has_master_tables` first rather than assume a
        partial result is usable."""
        with self._lock:
            if self._producto_table is None:
                return None, None, None
            return self._producto_table, self._representantes_table, self._convenios_table

    def set_reconocimiento_total(self, session_id: str, total: float) -> None:
        with self._lock:
            self._get_or_create(session_id)["reconocimiento_total"] = total

    def get_reconocimiento_total(self, session_id: str):
        with self._lock:
            return self._get_or_create(session_id)["reconocimiento_total"]

    def set_resultado(self, session_id: str, df) -> None:
        with self._lock:
            self._get_or_create(session_id)["resultado"] = df

    def get_resultado(self, session_id: str):
        with self._lock:
            return self._get_or_create(session_id)["resultado"]

    def reset(self, session_id: str) -> None:
        """Clears this session's ventas/resultado only -- master tables are
        global and intentionally survive a reset (use a fresh upload to
        replace them, not reiniciar)."""
        with self._lock:
            self._sessions.pop(session_id, None)
