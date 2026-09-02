"""Regression test for a real bug found while manually testing the notebook:
a broken environment (a dependency listed in requirements.txt but not
actually installed) made `build_namespace()` raise on worker startup, and the
parent process had no way to tell that apart from a slow cell -- it just
waited out the full CELL_TIMEOUT_SECONDS and told the user "your code timed
out" while silently discarding the whole session. worker_loop() must instead
report the real failure immediately, so WorkerManager.execute() surfaces it
like any other cell error rather than raising TimeoutError.

Calls worker_loop() directly (not through multiprocessing.Process) with
plain queue.Queue objects -- worker_loop only calls .get()/.put() on them, so
this exercises the exact same code path without the cost/flakiness of a real
subprocess.
"""
import queue
from unittest.mock import patch

from app.notebook.worker import worker_loop


def test_reports_a_build_namespace_failure_as_a_clear_error_instead_of_hanging():
    input_q = queue.Queue()
    output_q = queue.Queue()

    def _broken_build_namespace():
        raise ModuleNotFoundError("No module named 'seaborn'")

    with patch("app.notebook.execution.build_namespace", _broken_build_namespace):
        worker_loop(input_q, output_q, mem_bytes=0, cpu_seconds=1)

    result = output_q.get_nowait()
    assert result["error"]["type"] == "ModuleNotFoundError"
    assert "seaborn" in result["error"]["message"]
    # Must be framed as a server problem, not "your code" -- this is the
    # whole point of the fix.
    assert "servidor" in result["error"]["message"]
    assert "no es un error en tu código" in result["error"]["message"]


def test_normal_startup_still_processes_messages_as_before():
    input_q = queue.Queue()
    output_q = queue.Queue()
    input_q.put({"type": "exec", "code": "1 + 1"})
    input_q.put(None)  # shutdown signal so the loop returns

    worker_loop(input_q, output_q, mem_bytes=0, cpu_seconds=1)

    result = output_q.get_nowait()
    assert result["error"] is None
    assert result["result_text"] == "2"
