"""Lifecycle owner for all per-session, in-memory state: execution workers,
pending Excel uploads awaiting cleanup confirmation, and NL-assistant usage
counts (Story 6.2).

This is the ONLY place that creates, reuses, times-out and kills workers, and
the only place that tracks the other two. Routes never touch worker
processes directly. Keeping every session-keyed concern behind one lock and
one TTL-reap sweep (`_reap_idle`) keeps the concurrency reasoning in a
single, testable spot, rather than one lock per concern.

Concurrency note: the manager lives in-process, so a session is bound to the
process that created it. Under Gunicorn the service must therefore run with a
single worker process (and multiple threads for concurrency) — see the
backend Dockerfile CMD. For the MVP's 2-3 users this is more than enough.
"""
import multiprocessing as mp
import queue
import threading
import time

from app.notebook.worker import worker_loop

# Defaults; overridable from app config / environment.
DEFAULT_EXEC_TIMEOUT_SECONDS = 15
DEFAULT_MEM_BYTES = 512 * 1024 * 1024  # 512 MB
DEFAULT_CPU_SECONDS = 20
IDLE_TTL_SECONDS = 30 * 60  # reap sessions idle for 30 minutes
DEFAULT_ASSISTANT_MAX_REQUESTS = 20  # NL assistant requests per session (Story 6.2, NFR11)


class WorkerHandle:
    def __init__(self, ctx, mem_bytes, cpu_seconds):
        self.input_q = ctx.Queue()
        self.output_q = ctx.Queue()
        self.process = ctx.Process(
            target=worker_loop,
            args=(self.input_q, self.output_q, mem_bytes, cpu_seconds),
            daemon=True,
        )
        self.process.start()
        self.last_used = time.time()
        self.lock = threading.Lock()

    def is_alive(self):
        return self.process.is_alive()

    def send(self, message, timeout):
        """Send a message and wait for the single reply, killing on timeout."""
        self.last_used = time.time()
        self.input_q.put(message)
        try:
            return self.output_q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("La ejecución superó el límite de tiempo permitido.")

    def terminate(self):
        try:
            self.input_q.put(None)
        except Exception:
            pass
        if self.process.is_alive():
            self.process.terminate()
        try:
            self.process.join(timeout=3)
        except Exception:
            pass


class WorkerManager:
    def __init__(
        self,
        exec_timeout=DEFAULT_EXEC_TIMEOUT_SECONDS,
        mem_bytes=DEFAULT_MEM_BYTES,
        cpu_seconds=DEFAULT_CPU_SECONDS,
        idle_ttl=IDLE_TTL_SECONDS,
        assistant_max_requests=DEFAULT_ASSISTANT_MAX_REQUESTS,
    ):
        # "spawn" behaves the same on Windows and Linux, avoiding fork pitfalls
        # with matplotlib / threads inside the Flask process.
        self._ctx = mp.get_context("spawn")
        self._workers = {}
        self._pending_uploads = {}
        self._assistant_usage = {}  # session_id -> (count, last_used) - Story 6.2
        self._lock = threading.Lock()
        self.exec_timeout = exec_timeout
        self.mem_bytes = mem_bytes
        self.cpu_seconds = cpu_seconds
        self.idle_ttl = idle_ttl
        self.assistant_max_requests = assistant_max_requests

    def _reap_idle(self):
        """Caller must hold self._lock. Sweeps workers, pending uploads, and
        assistant-usage counts -- a session that only ever stages an upload
        (never calls execute/bind) or only ever asks the assistant would
        otherwise never pass through this reap at all.
        """
        now = time.time()
        stale = [
            sid
            for sid, w in self._workers.items()
            if now - w.last_used > self.idle_ttl or not w.is_alive()
        ]
        for sid in stale:
            self._workers.pop(sid).terminate()

        # Unlike _workers above, these two are plain (session_id -> tuple)
        # dicts with no extra teardown beyond a pop -- share the sweep.
        self._pop_stale(self._pending_uploads, now, last_active_at=lambda entry: entry[3])
        self._pop_stale(self._assistant_usage, now, last_active_at=lambda entry: entry[1])

    def _pop_stale(self, mapping, now, last_active_at):
        """Drop entries from `mapping` whose `last_active_at(entry)` predates
        `self.idle_ttl`. `mapping` is mutated in place."""
        stale_ids = [sid for sid, entry in mapping.items() if now - last_active_at(entry) > self.idle_ttl]
        for sid in stale_ids:
            mapping.pop(sid, None)

    def check_and_increment_assistant_usage(self, session_id):
        """Returns True and counts this request if the session is still
        under `assistant_max_requests`, False otherwise (Story 6.2, NFR11).

        Deliberately NOT reset by restart() -- resetting it there would let
        a user bypass the limit for free via the existing "Reiniciar sesión"
        button (Story 1.6), defeating the whole point of this limit. Only
        idle-TTL reaping clears it, matching genuine session abandonment.
        """
        with self._lock:
            self._reap_idle()
            count, _ = self._assistant_usage.get(session_id, (0, time.time()))
            if count >= self.assistant_max_requests:
                return False
            self._assistant_usage[session_id] = (count + 1, time.time())
            return True

    def release_assistant_usage(self, session_id):
        """Refund one unit of assistant quota for `session_id` - call this
        when a reserved request never actually reached the LLM (an
        InterpreterUnavailableError, not the user's fault: missing API key,
        provider outage, etc.), so our own unavailability doesn't
        permanently eat into a user's budget. A no-op if the session has no
        recorded usage yet.
        """
        with self._lock:
            entry = self._assistant_usage.get(session_id)
            if entry is None:
                return
            count, last_used = entry
            self._assistant_usage[session_id] = (max(0, count - 1), last_used)

    def _get_or_create(self, session_id):
        with self._lock:
            self._reap_idle()
            worker = self._workers.get(session_id)
            if worker is None or not worker.is_alive():
                if worker is not None:
                    worker.terminate()
                worker = WorkerHandle(self._ctx, self.mem_bytes, self.cpu_seconds)
                self._workers[session_id] = worker
            return worker

    def execute(self, session_id, code):
        worker = self._get_or_create(session_id)
        with worker.lock:  # serialise cells within one session
            try:
                return worker.send({"type": "exec", "code": code}, self.exec_timeout)
            except TimeoutError as exc:
                # A timed-out worker is in an unknown state: drop it so the next
                # cell starts fresh rather than reusing a poisoned process.
                self.restart(session_id)
                return {
                    "stdout": "",
                    "result_html": None,
                    "result_text": None,
                    "image_base64": None,
                    "error": {
                        "type": "TimeoutError",
                        "message": str(exc),
                        "traceback": "",
                    },
                    "session_restarted": True,
                }

    def execute_challenge(self, session_id, code, challenge_id):
        """Run a guided-lesson challenge: execute the learner's code, then --
        only if it ran without error -- check it in-place against the same
        live namespace. Returns the normal cell-result fields plus a
        ``challenge`` field ({"passed", "message"} or None if not checked).
        """
        worker = self._get_or_create(session_id)
        with worker.lock:
            try:
                exec_result = worker.send({"type": "exec", "code": code}, self.exec_timeout)
            except TimeoutError as exc:
                self.restart(session_id)
                return {
                    "stdout": "",
                    "result_html": None,
                    "result_text": None,
                    "image_base64": None,
                    "error": {"type": "TimeoutError", "message": str(exc), "traceback": ""},
                    "session_restarted": True,
                    "challenge": None,
                }

            if exec_result.get("error"):
                return {**exec_result, "challenge": None}

            try:
                challenge = worker.send({"type": "check", "challenge_id": challenge_id}, self.exec_timeout)
            except TimeoutError as exc:
                self.restart(session_id)
                challenge = {"passed": False, "message": f"Tiempo agotado al verificar ({exc})."}

            return {**exec_result, "challenge": challenge}

    def bind(self, session_id, name, value):
        worker = self._get_or_create(session_id)
        with worker.lock:
            return worker.send({"type": "bind", "name": name, "value": value}, self.exec_timeout)

    def stage_pending_upload(self, session_id, variable, df, profile):
        """Hold an uploaded DataFrame until the user confirms the proposed
        cleanup (Story 4.2) instead of binding it right away. Uploading again
        before confirming simply replaces whatever was pending.

        `profile` is the raw dict from excel_profiler.profile_excel() (minus
        the "dataframe" entry is fine either way, callers don't rely on it
        being stripped) - kept alongside the DataFrame so confirm_excel_cleanup
        can hand the column-type profile back to the frontend too. Without
        this, Epic 5's "Gráfica sin código" panel has no column list to show
        for any Excel that went through the cleanup-confirmation flow.
        """
        with self._lock:
            self._reap_idle()
            self._pending_uploads[session_id] = (variable, df, profile, time.time())

    def pop_pending_upload(self, session_id):
        """Return and clear the pending (variable, df, profile) for this session, or None."""
        with self._lock:
            entry = self._pending_uploads.pop(session_id, None)
        if entry is None:
            return None
        variable, df, profile, _staged_at = entry
        return variable, df, profile

    def discard_pending_upload(self, session_id):
        with self._lock:
            self._pending_uploads.pop(session_id, None)

    def restart(self, session_id):
        with self._lock:
            worker = self._workers.pop(session_id, None)
            self._pending_uploads.pop(session_id, None)
        if worker is not None:
            worker.terminate()
        return True

    def shutdown_all(self):
        with self._lock:
            for worker in self._workers.values():
                worker.terminate()
            self._workers.clear()
