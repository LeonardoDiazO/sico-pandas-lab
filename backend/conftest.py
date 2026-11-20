import flask
import pytest
from flask.testing import FlaskClient

from app.convatec import master_tables_store
from app.utils import secrets as app_secrets

SESSION_HEADER = "X-Session-Id"
_DEFAULT_LABEL = "__default__"


class TokenForwardingClient(FlaskClient):
    """Sessions are now minted by the server (app/utils/session.py): the
    first `/api/*` response carries a signed token in `X-Session-Id` and the
    client must send it back. Older tests pass their own labels
    ("session-a", "session-b") or no header at all - this client keeps one
    real token per label, so those labels still mean "the same session" /
    "a different session" exactly as before. A header that already is a
    validly signed token is sent untouched."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tokens = {}

    def open(self, *args, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        label = headers.get(SESSION_HEADER) or _DEFAULT_LABEL
        if label in self._tokens:
            headers[SESSION_HEADER] = self._tokens[label]
        elif label != _DEFAULT_LABEL and not self._looks_signed(label):
            headers.pop(SESSION_HEADER, None)
        kwargs["headers"] = headers
        response = super().open(*args, **kwargs)
        issued = response.headers.get(SESSION_HEADER)
        if issued:
            self._tokens[label] = issued
        return response

    def _looks_signed(self, value):
        from app.utils.session import unsign_session_id

        with self.application.app_context():
            return unsign_session_id(value) is not None


flask.Flask.test_client_class = TokenForwardingClient


@pytest.fixture(autouse=True)
def _isolate_convatec_master_tables_store(tmp_path, monkeypatch):
    """Every test gets its own throwaway directory for the persisted
    Convatec master tables -- otherwise test runs would read/write the real
    `backend/instance/convatec/` data seeded from Convatec's actual files."""
    monkeypatch.setattr(master_tables_store, "DATA_DIR", tmp_path / "convatec")


@pytest.fixture(autouse=True)
def _no_real_secrets(monkeypatch):
    """Tests never run with the developer's real secrets (GEMINI_API_KEY,
    APP_ACCESS_KEY, ...): create_app() captures them from os.environ into a
    process cache, so both places are cleared before every test."""
    for name in app_secrets.SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    app_secrets.reset_captured_secrets()
    yield
    app_secrets.reset_captured_secrets()
