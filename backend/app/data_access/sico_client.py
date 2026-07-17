"""Read-only access to the sico (`sco`) schema on the RDS MariaDB.

Every table in the `sco` schema is available — the boundary is the schema
itself, not a hand-picked subset of tables. The tool's job is to get real data
into a DataFrame with as little friction as possible; combining tables (joins),
grouping, and everything past that is meant to happen in pandas, in the user's
own code — that is the actual skill this app exists to practice, so we do not
pre-build SQL joins for them.

Hard constraints baked in here (defence in depth, on top of session-level
read-only — see _engine()):
  * Only tables that actually exist in the `sco` schema can ever be queried
    (validated dynamically against INFORMATION_SCHEMA, not a fixed list).
  * Only SELECT statements are ever built — no string comes from the user.
  * Every connection is put into READ ONLY mode before running anything.
  * Credentials live only in this process, sourced from environment variables,
    and are never handed to the execution worker (it only receives the
    resulting DataFrame). This satisfies FR20 / FR7 / FR21.
"""
import os
import time

import pandas as pd

SCHEMA = "sco"
DEFAULT_ROW_LIMIT = 500

# The full schema has ~460 tables. Most are noise for a pandas-practice tool:
# hundreds of ad-hoc personal scratch tables (temporal_<nombre>, temp_*, tem_*)
# and per-transaction tables (pos_<numero>_1). Views (vista_*/vist_*/v_*) are
# excluded too since they are not base tables. Everything else — the real
# business tables — stays visible. Decision made explicitly with the user
# after seeing the full list (2026-07-12).
_EXCLUDED_PREFIXES = ("temporal_", "temp_", "tem_", "pos_", "vista_", "vist_", "v_")


def _is_excluded(table_name):
    lowered = table_name.lower()
    return lowered.startswith(_EXCLUDED_PREFIXES)

# Table list changes rarely; avoid round-tripping to the RDS on every request.
_TABLES_CACHE = {"tables": None, "fetched_at": 0}
_TABLES_CACHE_TTL_SECONDS = 300


class SicoNotConfigured(RuntimeError):
    """Raised when the RDS connection env vars are missing."""


def _qualified(table):
    # Backticks are required because several identifiers start with digits.
    return f"`{SCHEMA}`.`{table}`"


def is_configured():
    return bool(os.environ.get("SICO_DB_HOST") and os.environ.get("SICO_DB_USER"))


_ENGINE = None


def _engine():
    """Return a cached SQLAlchemy engine whose every connection is READ ONLY.

    Because the project connects with the shared privileged account (no
    dedicated read-only user exists), session-level read-only is the primary
    write-protection: a "SET SESSION TRANSACTION READ ONLY" is applied to every
    physical connection as it is created, so MariaDB rejects any INSERT/UPDATE/
    DELETE/DDL on that session even for a privileged user.
    """
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    from sqlalchemy import create_engine, event

    host = os.environ.get("SICO_DB_HOST")
    user = os.environ.get("SICO_DB_USER")
    password = os.environ.get("SICO_DB_PASSWORD", "")
    port = os.environ.get("SICO_DB_PORT", "3306")
    if not host or not user:
        raise SicoNotConfigured(
            "La conexión a la base de datos de sico no está configurada "
            "(faltan variables SICO_DB_*)."
        )
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{SCHEMA}"
    connect_args = {"connect_timeout": int(os.environ.get("SICO_DB_CONNECT_TIMEOUT", "10"))}
    if os.environ.get("SICO_DB_SSL", "").lower() in ("1", "true", "require"):
        connect_args["ssl"] = {"ssl": True}

    # pool_recycle avoids reusing a connection the RDS has already dropped after
    # an idle period; pool_pre_ping validates a connection before handing it out.
    engine = create_engine(
        url, pool_pre_ping=True, pool_recycle=280, connect_args=connect_args
    )

    @event.listens_for(engine, "connect")
    def _force_read_only(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        finally:
            cur.close()

    _ENGINE = engine
    return _ENGINE


def assert_select_only(sql):
    """Hard guard: refuse to run anything that is not a plain SELECT.

    Structural belt-and-suspenders so no write statement can ever leave this
    module, even by future mistake. Raises ValueError otherwise.
    """
    stripped = sql.lstrip().lstrip("(").lstrip().upper()
    if not stripped.startswith("SELECT"):
        raise ValueError("Solo se permiten consultas SELECT contra la base de datos.")
    # No stacked statements.
    if ";" in sql.rstrip().rstrip(";"):
        raise ValueError("No se permiten múltiples sentencias.")
    return sql


def _with_retry(fn, attempts=2, delay_seconds=1.5):
    """Retry a DB call once on a transient connection error.

    The RDS connection from this network is known to be intermittent (some
    attempts time out, the very next one succeeds) — see architecture notes.
    A single short retry smooths that over instead of surfacing a scary error
    for what is usually a one-off blip.
    """
    from sqlalchemy.exc import OperationalError

    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OperationalError as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise last_exc


def _read_sql(sql, params=None):
    """Run a SELECT on a connection that is already forced into READ ONLY."""
    from sqlalchemy import text

    assert_select_only(sql)

    def _run():
        engine = _engine()
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)

    return _with_retry(_run)


def _fetch_table_names():
    """Ask MariaDB which tables actually exist in the sco schema, right now."""
    from sqlalchemy import text

    def _run():
        engine = _engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME"
                ),
                {"schema": SCHEMA},
            ).fetchall()
        return [r[0] for r in rows]

    return _with_retry(_run)


def list_tables(force_refresh=False):
    """Business tables in the `sco` schema, cached briefly to avoid hammering the RDS.

    Excludes personal scratch tables, per-transaction tables and views (see
    _EXCLUDED_PREFIXES) — everything else in the schema is included.
    """
    now = time.time()
    cached = _TABLES_CACHE["tables"]
    if not force_refresh and cached is not None and now - _TABLES_CACHE["fetched_at"] < _TABLES_CACHE_TTL_SECONDS:
        names = cached
    else:
        names = [t for t in _fetch_table_names() if not _is_excluded(t)]
        _TABLES_CACHE["tables"] = names
        _TABLES_CACHE["fetched_at"] = now
    return [{"schema": SCHEMA, "table": t} for t in names]


def _validate(table):
    if _is_excluded(table):
        raise ValueError(f"Tabla no disponible para práctica: {table}")
    known = {t["table"] for t in list_tables()}
    if table not in known:
        raise ValueError(f"Tabla no encontrada en el esquema {SCHEMA}: {table}")


def load_table(table, limit=DEFAULT_ROW_LIMIT):
    """SELECT * FROM sco.<table> LIMIT n as a DataFrame.

    ``table`` is validated against the live table list before being
    interpolated, so only identifiers that genuinely exist in the schema can
    ever reach the query — this is what keeps the f-string below safe despite
    not being a bind parameter (table/column names cannot be bound in SQL).
    """
    _validate(table)
    limit = int(limit)
    sql = f"SELECT * FROM {_qualified(table)} LIMIT {limit}"
    return _read_sql(sql)
