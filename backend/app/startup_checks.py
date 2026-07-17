"""Startup guard: refuse to run with a database user that can write.

FR21 / non-negotiable security requirement. Rather than trusting that someone
remembered to use a read-only account, we ask the database what privileges the
configured user actually holds and abort boot if anything beyond SELECT shows
up on a relevant table/schema.

The privilege *evaluation* is a pure function (evaluate_privileges) so it can
be unit tested without a live database; the DB fetch is a thin separate layer.
"""

# Any privilege that is not exactly read access is a hard stop.
_READ_ONLY = {"SELECT", "USAGE"}


class ReadOnlyViolation(RuntimeError):
    """Raised when the DB user holds write privileges. Boot must abort."""


def evaluate_privileges(privilege_names):
    """Return the sorted list of offending (non-read) privileges.

    Accepts an iterable of privilege strings as reported by
    INFORMATION_SCHEMA (e.g. "SELECT", "INSERT", "UPDATE", "ALL PRIVILEGES").
    An empty result means the user is read-only.
    """
    offending = set()
    for raw in privilege_names:
        name = (raw or "").strip().upper()
        if not name:
            continue
        if name == "ALL PRIVILEGES" or name not in _READ_ONLY:
            offending.add(name)
    return sorted(offending)


def decide_guard(offending, allow_write_user):
    """Pure decision for the startup guard.

    Returns (verdict, message) where verdict is one of:
      * "ok"        - user is read-only, all good.
      * "degraded"  - user can write, but the operator explicitly opted in to
                      using a privileged account; boot continues relying on
                      session-level READ ONLY as the write-protection.
      * "abort"     - user can write and no opt-in; boot must stop.
    """
    if not offending:
        return "ok", "read-only verificado"
    privs = ", ".join(offending)
    if allow_write_user:
        return (
            "degraded",
            "ATENCIÓN: el usuario de base de datos tiene privilegios de escritura ("
            + privs
            + "). Se acepta por SICO_ALLOW_WRITE_USER=true; la escritura se bloquea "
            "a nivel de sesión (SET SESSION TRANSACTION READ ONLY) en cada conexión.",
        )
    return (
        "abort",
        "El usuario de base de datos configurado tiene privilegios de escritura ("
        + privs
        + "). El servicio no arranca. Usa un usuario solo-lectura (SELECT) o, si "
        "vas a conectar con una cuenta privilegiada a propósito, define "
        "SICO_ALLOW_WRITE_USER=true.",
    )


def verify_read_only(fetch_privileges, allow_write_user=False):
    """Run the check against a privilege source.

    ``fetch_privileges`` is a zero-arg callable returning an iterable of
    privilege strings. Injecting it keeps this testable and keeps the DB
    driver out of the pure logic. Raises ReadOnlyViolation only on "abort".
    """
    verdict, message = decide_guard(
        evaluate_privileges(fetch_privileges()), allow_write_user
    )
    if verdict == "abort":
        raise ReadOnlyViolation(message)
    return verdict, message


def _fetch_privileges_from_db():
    """Ask MariaDB what the configured user is granted, via SHOW GRANTS.

    SHOW GRANTS is available to every user for their own grants and is far more
    reliable than joining INFORMATION_SCHEMA privilege tables. Returns the list
    of privilege tokens (e.g. ["ALL PRIVILEGES"] or ["SELECT", "INSERT"]).
    """
    from app.data_access.sico_client import _engine

    engine = _engine()
    privileges = []
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SHOW GRANTS").fetchall()
    for row in rows:
        line = (row[0] or "").upper()
        # e.g. "GRANT SELECT, INSERT ON `sco`.* TO ..." -> take between GRANT and ON
        if "GRANT " not in line or " ON " not in line:
            continue
        segment = line.split("GRANT ", 1)[1].split(" ON ", 1)[0]
        for token in segment.split(","):
            privileges.append(token.strip())
    return privileges


def run_read_only_guard():
    """Called at app startup. Only enforces when the RDS is configured.

    If the sico connection is not configured (e.g. running the Excel-only demo
    locally), there is nothing to check and boot proceeds. If the privilege
    query itself fails, we do not hard-crash boot when the operator has opted
    in to a privileged account (session read-only is still enforced); otherwise
    we surface a clear message.
    """
    import os

    from app.data_access.sico_client import is_configured

    if not is_configured():
        return "skipped: sico DB not configured"

    allow_write = os.environ.get("SICO_ALLOW_WRITE_USER", "").lower() in ("1", "true")
    try:
        _verdict, message = verify_read_only(_fetch_privileges_from_db, allow_write)
        return message
    except ReadOnlyViolation:
        raise
    except Exception as exc:  # noqa: BLE001 - privilege check failed to run
        if allow_write:
            return (
                "no se pudo verificar privilegios ("
                + str(exc)
                + "); se continúa porque SICO_ALLOW_WRITE_USER=true. La escritura "
                "sigue bloqueada a nivel de sesión."
            )
        raise ReadOnlyViolation(
            "No se pudieron verificar los privilegios del usuario de base de datos ("
            + str(exc)
            + "). Si conectas con una cuenta privilegiada a propósito, define "
            "SICO_ALLOW_WRITE_USER=true."
        ) from exc
