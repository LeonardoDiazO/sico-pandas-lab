"""Per-session in-memory storage for uploaded files and the last processed result.

Deliberately simpler than notebook.WorkerManager -- there is no code execution
to sandbox here, just DataFrames to hold between requests for one session id.
Session id lifetime is whatever `SessionService` on the frontend gives it
(currently a `localStorage` value -- shared across every tab of the same
browser profile, not per-tab; matches the rest of sico-pandas-lab today, see
`frontend/src/app/core/session.service.ts`).

PRD S5.3 `[ASSUMPTION]`: nothing here survives a process restart; there is no
persistence layer for this demo iteration.

Every public method takes the lock for its entire read-modify-write, not
just the initial `setdefault` -- an earlier version only locked the
dictionary lookup and mutated the session's own dict afterwards unlocked,
which two concurrent requests for the same session id could race (found in
code review).
"""
import threading


class ConvatecSessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}

    def _get_or_create(self, session_id: str) -> dict:
        return self._sessions.setdefault(
            session_id,
            {
                "producto_table": None,
                "representantes_table": None,
                "convenios_table": None,
                "ventas": {},  # {"productos" | "servicios" | "envios_nacionales": DataFrame}
                "resultado": None,
            },
        )

    def set_master_tables(self, session_id: str, producto_table, representantes_table, convenios_table) -> None:
        with self._lock:
            state = self._get_or_create(session_id)
            # FR-3: a fresh upload replaces the whole previous set, no partial merge.
            state["producto_table"] = producto_table
            state["representantes_table"] = representantes_table
            state["convenios_table"] = convenios_table

    def has_master_tables(self, session_id: str) -> bool:
        with self._lock:
            state = self._get_or_create(session_id)
            return all(
                state[key] is not None
                for key in ("producto_table", "representantes_table", "convenios_table")
            )

    def set_ventas(self, session_id: str, tipo: str, df) -> None:
        with self._lock:
            self._get_or_create(session_id)["ventas"][tipo] = df

    def get_ventas(self, session_id: str, tipo: str):
        with self._lock:
            return self._get_or_create(session_id)["ventas"].get(tipo)

    def master_tables(self, session_id: str):
        """Returns (producto_table, representantes_table, convenios_table),
        or (None, None, None) if any hasn't been uploaded yet -- callers
        should check `has_master_tables` first rather than assume a partial
        result is usable."""
        with self._lock:
            state = self._get_or_create(session_id)
            if not all(
                state[key] is not None
                for key in ("producto_table", "representantes_table", "convenios_table")
            ):
                return None, None, None
            return state["producto_table"], state["representantes_table"], state["convenios_table"]

    def set_resultado(self, session_id: str, df) -> None:
        with self._lock:
            self._get_or_create(session_id)["resultado"] = df

    def get_resultado(self, session_id: str):
        with self._lock:
            return self._get_or_create(session_id)["resultado"]

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
