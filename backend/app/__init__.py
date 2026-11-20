import atexit
import secrets as _stdlib_secrets

from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from app.config import Config, runtime_settings
from app.utils.api_response import api_response
from app.utils.secrets import capture_secrets

# Used only when SECRET_KEY is not configured (local development): one random
# key per process, so every create_app() in the same process (tests, reloads)
# signs and verifies session tokens the same way. Tokens die with the
# process, exactly like the in-memory notebook workers they point to.
_FALLBACK_SECRET_KEY = _stdlib_secrets.token_hex(32)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Secrets are captured into app.config and REMOVED from os.environ before
    # any notebook worker is spawned, so a worker process is born without
    # them (see app/utils/secrets.py for why scrubbing inside the child is
    # not enough on Linux).
    app.config.update(capture_secrets())
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _FALLBACK_SECRET_KEY

    settings = runtime_settings()
    app.config.update(settings)
    app.config["MAX_CONTENT_LENGTH"] = settings["MAX_UPLOAD_MB"] * 1024 * 1024

    # The shared team key (APP_ACCESS_KEY) is the access control now, so CORS
    # stays open; X-Session-Id must be exposed so the browser can read the
    # server-issued session token.
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        expose_headers=["X-Session-Id"],
    )

    from app.utils.session import access_key_required, init_session

    init_session(app)

    # Single in-process manager owns every session's execution worker.
    from app.notebook.worker_manager import CapacityError, WorkerManager

    manager = WorkerManager(
        exec_timeout=settings["CELL_TIMEOUT_SECONDS"],
        assistant_max_requests=settings["ASSISTANT_MAX_REQUESTS_PER_SESSION"],
        assistant_max_requests_per_day=settings["ASSISTANT_MAX_REQUESTS_PER_DAY"],
        max_sessions=settings["MAX_SESSIONS"],
    )
    app.config["WORKER_MANAGER"] = manager
    # Reap every session's execution process on a clean shutdown so we don't
    # leave orphaned worker processes behind.
    atexit.register(manager.shutdown_all)

    @app.errorhandler(RequestEntityTooLarge)
    def _too_large(_exc):
        return api_response(
            message=f"El archivo supera el límite de {settings['MAX_UPLOAD_MB']} MB.",
            success=False,
            status=413,
        )

    @app.errorhandler(CapacityError)
    def _capacity(_exc):
        return api_response(
            message="El servidor está lleno, intenta en unos minutos.",
            success=False,
            status=503,
        )

    # FR21: refuse to boot if the configured DB user can write. Skipped when
    # the RDS is not configured (Excel-only local demo).
    from app.startup_checks import run_read_only_guard

    with app.app_context():
        guard_result = run_read_only_guard()
    app.logger.info("read-only guard: %s", guard_result)

    @app.get("/api/health")
    def health():
        return api_response(
            data={
                "service": "sico-pandas-lab-backend",
                "readOnlyGuard": guard_result,
                "accessKeyRequired": access_key_required(),
                "maxUploadMb": settings["MAX_UPLOAD_MB"],
            },
            message="ok",
        )

    # Convatec (client-specific commission/assignment module) is disconnected
    # on request -- unrelated to the pandas-learning product this app is
    # otherwise focused on. Code and tests are left in place on disk in case
    # the Convatec demo work resumes later; see test_convatec_routes.py's
    # module-level skip for the matching test-side decision.
    # from app.convatec.session_store import ConvatecSessionStore
    # app.config["CONVATEC_SESSION_STORE"] = ConvatecSessionStore()
    # from app.convatec.routes import convatec_bp
    # app.register_blueprint(convatec_bp)

    from app.data_access.routes import data_bp
    from app.guided.routes import guided_bp
    from app.notebook.routes import notebook_bp

    app.register_blueprint(notebook_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(guided_bp)

    return app
