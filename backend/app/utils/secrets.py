"""Single place where secrets are read from the process environment.

Why this exists (security hardening, 2026-11): every notebook cell runs in a
worker process spawned from the Flask process. A spawned child inherits the
parent's environment block, and on Linux `/proc/self/environ` (and
`/proc/<ppid>/environ`) keeps exposing the *initial* block even after
`os.environ.pop()` in the child. So the only reliable fix is that the
secrets are no longer in the parent's environment when the first worker is
created: `capture_secrets()` (called from `create_app()`) copies them into
`app.config` and REMOVES them from `os.environ`.

Rules for the rest of the package:
- never evaluate a secret at import time (the worker imports the `app`
  package too);
- read secrets with `get_secret()`, which prefers `current_app.config`.
"""
import os

from flask import current_app, has_app_context

SECRET_NAMES = (
    "SECRET_KEY",
    "APP_ACCESS_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "SICO_DB_HOST",
    "SICO_DB_PORT",
    "SICO_DB_USER",
    "SICO_DB_PASSWORD",
    "SICO_DB_SSL",
    "SICO_DB_CONNECT_TIMEOUT",
    "SICO_ALLOW_WRITE_USER",
)

# Values already removed from os.environ by an earlier create_app() call in
# this same process (tests and `flask` reloads build the app more than once).
_captured = {}


def capture_secrets():
    """Moves every known secret from os.environ into a process-local cache
    and returns {name: value} for the ones that are set. A value still (or
    again) present in os.environ wins over the cached one, so re-reading after
    an operator change keeps working."""
    for name in SECRET_NAMES:
        if name in os.environ:
            _captured[name] = os.environ.pop(name)
    return {name: value for name, value in _captured.items() if value not in (None, "")}


def reset_captured_secrets():
    """Test helper: forget every captured value."""
    _captured.clear()


def get_secret(name, default=None):
    """Inside a request/app context: the value captured into app.config.
    Outside one (scripts, unit tests calling a module directly): the
    captured cache, then os.environ."""
    if has_app_context():
        value = current_app.config.get(name)
    else:
        value = _captured.get(name, os.environ.get(name))
    return default if value in (None, "") else value
