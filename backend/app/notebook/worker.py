"""Child-process worker that keeps one user's notebook namespace alive.

One worker == one session. The worker holds a persistent namespace across cell
executions (so variables defined in cell 1 are available in cell 2), while
running in a separate OS process so a crash or runaway loop cannot take down
the Flask server or leak into another user's session.

Threat model (architecture doc, Decision #1): this sandbox protects against
ACCIDENTS and CASUAL ABUSE by people who have the team key - a runaway loop,
`import os`, `open('/etc/passwd')`, `pd.read_csv('/proc/self/environ')`,
`pd.read_pickle(...)`. It is NOT a defense against a determined attacker:
Python's object model has known escapes (for example `pd.__builtins__` still
reaches the real builtins). Layers, in order:

1. The Flask process removes every secret from its own environment before
   spawning any worker (app/utils/secrets.py), so the worker is born without
   GEMINI_API_KEY/SECRET_KEY/SICO_DB_* - and `/proc/<pid>/environ` of either
   process no longer has them.
2. `_harden_process()` scrubs anything secret-looking that is still in the
   worker's environment (defense in depth) and wraps the file/URL/pickle I/O
   of pandas/numpy/matplotlib (execution.install_io_guards).
3. Cells run with a COPY of the builtins: filtered `__import__` (allowlist)
   and no open/exec/eval/compile/input/breakpoint (execution.build_namespace).
4. Resource limits via resource.setrlimit on POSIX (Render/Linux); on Windows
   dev machines the limits are skipped with no error.

Moving to container isolation (gVisor/CodeJail) is the documented Growth
upgrade if the user base or trust level changes.
"""
import multiprocessing
import os
import re
import traceback

# Environment variable names that look like credentials. Matched against the
# upper-cased name.
_SECRET_ENV_PATTERN = re.compile(
    r"(KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|^SICO_DB_|^AWS_|^GEMINI|^GOOGLE_|DATABASE_URL)"
)


def _scrub_environment():
    for name in list(os.environ):
        if _SECRET_ENV_PATTERN.search(name.upper()):
            os.environ.pop(name, None)


def _harden_process():
    """Process-wide hardening. Only applied when actually running as a child
    worker process - tests call worker_loop() in the pytest process itself,
    where patching pandas and wiping the environment would leak into every
    other test."""
    if multiprocessing.parent_process() is None:
        return
    _scrub_environment()
    from app.notebook.execution import install_io_guards

    install_io_guards()


def _install_resource_limits(mem_bytes, cpu_seconds):
    """Cap CPU time so a runaway loop can't peg a core forever.

    We deliberately do NOT set RLIMIT_AS (virtual address space): numpy,
    pandas and matplotlib reserve large amounts of virtual memory and an
    RLIMIT_AS cap makes them fail or thrash. Actual memory is bounded at the
    container level instead (Render/ECS memory limit). The wall-clock timeout
    in WorkerManager handles hangs; RLIMIT_CPU handles busy loops.

    ``mem_bytes`` is accepted for interface stability but intentionally unused.
    """
    try:
        import resource
    except ImportError:
        return  # Windows dev machine - limits enforced only in Linux containers
    cpu = getattr(resource, "RLIMIT_CPU", None)
    if cpu is not None:
        try:
            resource.setrlimit(cpu, (cpu_seconds, cpu_seconds))
        except (ValueError, OSError):
            pass


def worker_loop(input_q, output_q, mem_bytes, cpu_seconds):
    """Run until told to stop. Each message is handled and answered in order."""
    _install_resource_limits(mem_bytes, cpu_seconds)

    from app.notebook.execution import build_namespace, execute_code

    try:
        _harden_process()
        namespace = build_namespace()
    except Exception as exc:
        # A broken environment (e.g. a dependency listed in requirements.txt
        # but not actually installed) must never look like "your code timed
        # out" -- that misleads a learner into thinking their code is slow or
        # wrong when the problem is the server's setup. Report it immediately
        # and exit; WorkerManager._get_or_create() will see this process is
        # dead and spin up a fresh one on the next attempt.
        output_q.put(
            {
                "stdout": "",
                "result_html": None,
                "result_text": None,
                "result_records": None,
                "chart_svg": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": (
                        "El entorno de ejecución no pudo iniciar (esto no es un error en "
                        f"tu código, es un problema del servidor): {exc}"
                    ),
                    "traceback": traceback.format_exc(),
                },
            }
        )
        return

    # Untouched copies of every DataFrame the backend injected (`bind`), kept
    # OUTSIDE the learner's namespace: guided-lesson checkers compare the
    # learner's answer against these, so replacing/mutating `df` before
    # assigning an answer can't make a challenge pass. Private by convention
    # only (same process as the learner) - enough for the threat model above.
    pristine = {}

    while True:
        message = input_q.get()
        if message is None:  # shutdown signal
            break

        kind = message.get("type")
        reply_id = message.get("__id")

        def reply(result, _id=reply_id):
            # Echo the request's sequence number (see WorkerHandle.send).
            if isinstance(result, dict) and _id is not None:
                result = {**result, "__reply_to": _id}
            output_q.put(result)

        if kind == "exec":
            reply(execute_code(message["code"], namespace))
        elif kind == "bind":
            # Inject a value (e.g. a DataFrame loaded from Excel or the RDS)
            # under a variable name the user can reference in their cells.
            value = message["value"]
            namespace[message["name"]] = value
            pristine[message["name"]] = value.copy() if hasattr(value, "copy") else value
            reply({"bound": message["name"]})
        elif kind == "check":
            # Runs a guided-lesson challenge checker against the learner's own
            # live namespace, right here in the sandboxed process -- the
            # checker logic never leaves the backend, so the answer isn't
            # visible from the browser's network tab.
            from app.guided.challenges import run_checker

            reply(
                run_checker(
                    message["challenge_id"],
                    namespace,
                    message.get("context"),
                    pristine=pristine,
                    had_chart=bool(message.get("had_chart")),
                )
            )
        else:
            reply({"error": {"type": "ProtocolError", "message": f"tipo desconocido: {kind}", "traceback": ""}})
