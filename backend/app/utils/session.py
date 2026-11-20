"""Server-issued, signed session ids and the shared team access key.

Before this module the browser invented its own session id (any string in
`X-Session-Id`, or "anonymous" when missing) - so anyone could pick, guess
or share someone else's id and land in their notebook worker. Now:

- the server is the only one who mints ids: every `/api/*` request without a
  valid signed token gets a fresh one, returned in the `X-Session-Id`
  RESPONSE header (exposed through CORS); the client stores it and sends it
  back on every following request;
- a token is only trusted when its `itsdangerous` signature (keyed by
  SECRET_KEY) checks out - routes never fall back to "anonymous";
- when `APP_ACCESS_KEY` is configured, every `/api/*` route except
  `/api/health` requires it in `X-Access-Key` (401 otherwise). When it is not
  configured (local development) nothing is required.
"""
import hmac
import uuid

from flask import current_app, g, request
from itsdangerous import BadSignature, Signer

from app.utils.api_response import api_response

SESSION_HEADER = "X-Session-Id"
ACCESS_HEADER = "X-Access-Key"
PUBLIC_PATHS = frozenset({"/api/health"})
ACCESS_DENIED_MESSAGE = "Ingresa la clave del equipo."
_SALT = "sico-pandas-lab.session"


def _signer():
    return Signer(current_app.config["SECRET_KEY"], salt=_SALT)


def sign_session_id(session_id):
    return _signer().sign(session_id.encode("utf-8")).decode("utf-8")


def unsign_session_id(token):
    """Returns the raw session id for a validly signed token, else None."""
    if not token or not isinstance(token, str):
        return None
    try:
        return _signer().unsign(token.encode("utf-8")).decode("utf-8")
    except (BadSignature, UnicodeError, ValueError):
        return None


def access_key_required():
    return bool(current_app.config.get("APP_ACCESS_KEY"))


def _access_key_ok():
    expected = current_app.config.get("APP_ACCESS_KEY")
    if not expected:
        return True
    provided = request.headers.get(ACCESS_HEADER, "")
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _before_request():
    if not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None
    if request.path not in PUBLIC_PATHS and not _access_key_ok():
        return api_response(message=ACCESS_DENIED_MESSAGE, success=False, status=401)

    session_id = unsign_session_id(request.headers.get(SESSION_HEADER))
    if session_id is None:
        session_id = uuid.uuid4().hex
        g.issued_session_token = sign_session_id(session_id)
    g.session_id = session_id
    return None


def _after_request(response):
    token = g.pop("issued_session_token", None)
    if token:
        response.headers[SESSION_HEADER] = token
    return response


def init_session(app):
    app.before_request(_before_request)
    app.after_request(_after_request)


def current_session_id():
    """The verified session id of the current request. Every `/api/*` request
    has one by the time a route runs (see _before_request)."""
    session_id = g.get("session_id")
    if session_id is None:  # pragma: no cover - only outside /api/* routes
        raise RuntimeError("No hay una sesión verificada para esta petición.")
    return session_id
