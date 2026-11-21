"""Tests for the assistant-usage rate limiting added to WorkerManager in
Story 6.2. Deliberately does NOT exercise the worker-process side of
WorkerManager (execute/bind/etc.) - check_and_increment_assistant_usage()
and restart() both only touch in-memory dicts under the manager's lock, so
these tests never spin up a real worker subprocess.
"""
import time

from app.notebook.worker_manager import WorkerManager


def test_allows_requests_up_to_the_configured_max():
    manager = WorkerManager(assistant_max_requests=3)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is True


def test_rejects_the_request_that_exceeds_the_max():
    manager = WorkerManager(assistant_max_requests=2)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False


def test_further_requests_after_the_limit_keep_being_rejected():
    manager = WorkerManager(assistant_max_requests=1)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False
    assert manager.check_and_increment_assistant_usage("s1") is False


def test_sessions_have_independent_counts():
    manager = WorkerManager(assistant_max_requests=1)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False
    # a different session is unaffected by s1 having hit its limit
    assert manager.check_and_increment_assistant_usage("s2") is True


def test_restart_does_not_reset_assistant_usage_count():
    """The most important test in this story - see the "Decisión de diseño
    crítica" note in the story file. If restart() reset this counter, any
    user could bypass the whole rate limit for free via the existing
    "Reiniciar sesión" button (Story 1.6), defeating NFR11's purpose."""
    manager = WorkerManager(assistant_max_requests=1)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False

    manager.restart("s1")

    assert manager.check_and_increment_assistant_usage("s1") is False


def test_release_assistant_usage_refunds_one_slot():
    """Regression test (Epic 6 code review): if a reserved request never
    actually reached the LLM (our own InterpreterUnavailableError, not the
    user's fault), it must not permanently eat into the session's budget."""
    manager = WorkerManager(assistant_max_requests=1)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False

    manager.release_assistant_usage("s1")

    assert manager.check_and_increment_assistant_usage("s1") is True


def test_release_assistant_usage_on_a_session_with_no_usage_is_a_no_op():
    manager = WorkerManager(assistant_max_requests=1)
    manager.release_assistant_usage("never-asked-anything")  # must not raise
    assert manager.check_and_increment_assistant_usage("never-asked-anything") is True


def test_reap_idle_clears_assistant_usage_for_stale_sessions(monkeypatch):
    manager = WorkerManager(assistant_max_requests=1, idle_ttl=100)
    assert manager.check_and_increment_assistant_usage("s1") is True
    assert manager.check_and_increment_assistant_usage("s1") is False

    real_now = time.time()
    monkeypatch.setattr(time, "time", lambda: real_now + 1000)
    # any call that triggers _reap_idle() should have forgotten s1 by now
    assert manager.check_and_increment_assistant_usage("s1") is True


def test_send_discards_a_stale_reply_from_a_timed_out_request():
    """Regression (live test, low-memory machine): a reply that arrived after
    its request timed out stayed in the queue, and every later request got
    the PREVIOUS answer (wrong cardinalities, $0 totals on the dashboard)."""
    import queue

    from app.notebook.worker_manager import WorkerHandle

    handle = WorkerHandle.__new__(WorkerHandle)
    handle.input_q = queue.Queue()
    handle.output_q = queue.Queue()
    handle._seq = 4
    # Late answer to request #4, still sitting in the queue...
    handle.output_q.put({"result_text": "respuesta vieja", "__reply_to": 4})
    # ...and the real answer to the next request (#5).
    handle.output_q.put({"result_text": "respuesta correcta", "__reply_to": 5})

    reply = handle.send({"type": "exec", "code": "1"}, timeout=2)

    assert reply == {"result_text": "respuesta correcta"}
    assert handle.input_q.get_nowait()["__id"] == 5


def test_send_accepts_the_start_up_failure_report_without_an_id():
    import queue

    from app.notebook.worker_manager import WorkerHandle

    handle = WorkerHandle.__new__(WorkerHandle)
    handle.input_q = queue.Queue()
    handle.output_q = queue.Queue()
    handle.output_q.put({"error": {"type": "ImportError", "message": "x", "traceback": ""}})
    assert handle.send({"type": "exec", "code": "1"}, timeout=2)["error"]["type"] == "ImportError"
