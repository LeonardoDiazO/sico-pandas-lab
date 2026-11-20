import os

DEFAULT_MAX_UPLOAD_MB = 15
DEFAULT_MAX_SESSIONS = 8
DEFAULT_ASSISTANT_MAX_REQUESTS_PER_SESSION = 20
DEFAULT_ASSISTANT_MAX_REQUESTS_PER_DAY = 200


class Config:
    """12-factor config: every setting is sourced from the environment.

    Only NON-secret settings may live here as class attributes: this module
    is imported by every worker process (the worker imports the `app`
    package), so anything evaluated at import time ends up in the memory of
    the process that runs user code. Secrets (SECRET_KEY, APP_ACCESS_KEY,
    GEMINI_API_KEY, SICO_DB_*) are read inside create_app() via
    app.utils.secrets.capture_secrets() instead.
    """

    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = ENV == "development"


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def runtime_settings():
    """Non-secret runtime limits, read when the app is created (not at import)."""
    return {
        "CELL_TIMEOUT_SECONDS": _int_env("CELL_TIMEOUT_SECONDS", 15),
        "MAX_UPLOAD_MB": _int_env("MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB),
        "MAX_SESSIONS": _int_env("MAX_SESSIONS", DEFAULT_MAX_SESSIONS),
        "ASSISTANT_MAX_REQUESTS_PER_SESSION": _int_env(
            "ASSISTANT_MAX_REQUESTS_PER_SESSION", DEFAULT_ASSISTANT_MAX_REQUESTS_PER_SESSION
        ),
        "ASSISTANT_MAX_REQUESTS_PER_DAY": _int_env(
            "ASSISTANT_MAX_REQUESTS_PER_DAY", DEFAULT_ASSISTANT_MAX_REQUESTS_PER_DAY
        ),
    }
