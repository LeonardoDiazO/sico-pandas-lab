"""Child-process worker that keeps one user's notebook namespace alive.

One worker == one session. The worker holds a persistent namespace across cell
executions (so variables defined in cell 1 are available in cell 2), while
running in a separate OS process so a crash or runaway loop cannot take down
the Flask server or leak into another user's session.

Threat model (see architecture doc): this protects against *accidents* by
trusted internal users, not against a determined attacker. Resource limits are
applied via resource.setrlimit on POSIX (Render/Linux); on Windows dev
machines the limits are skipped with no error.
"""


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

    namespace = build_namespace()

    while True:
        message = input_q.get()
        if message is None:  # shutdown signal
            break

        kind = message.get("type")
        if kind == "exec":
            output_q.put(execute_code(message["code"], namespace))
        elif kind == "bind":
            # Inject a value (e.g. a DataFrame loaded from Excel or the RDS)
            # under a variable name the user can reference in their cells.
            namespace[message["name"]] = message["value"]
            output_q.put({"bound": message["name"]})
        elif kind == "check":
            # Runs a guided-lesson challenge checker against the learner's own
            # live namespace, right here in the sandboxed process -- the
            # checker logic never leaves the backend, so the answer isn't
            # visible from the browser's network tab.
            from app.guided.challenges import run_checker

            output_q.put(run_checker(message["challenge_id"], namespace))
        else:
            output_q.put({"error": {"type": "ProtocolError", "message": f"tipo desconocido: {kind}", "traceback": ""}})
