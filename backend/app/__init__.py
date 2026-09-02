import atexit
import os

from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.utils.api_response import api_response


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # No auth in the MVP (open access), so CORS is permissive. When login is
    # added in Growth this should be tightened to the known frontend origin.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Single in-process manager owns every session's execution worker.
    from app.notebook.worker_manager import WorkerManager

    manager = WorkerManager(
        exec_timeout=int(os.environ.get("CELL_TIMEOUT_SECONDS", "15")),
        assistant_max_requests=int(os.environ.get("ASSISTANT_MAX_REQUESTS_PER_SESSION", "20")),
    )
    app.config["WORKER_MANAGER"] = manager
    # Reap every session's execution process on a clean shutdown so we don't
    # leave orphaned worker processes behind.
    atexit.register(manager.shutdown_all)

    # FR21: refuse to boot if the configured DB user can write. Skipped when
    # the RDS is not configured (Excel-only local demo).
    from app.startup_checks import run_read_only_guard

    guard_result = run_read_only_guard()
    app.logger.info("read-only guard: %s", guard_result)

    @app.get("/api/health")
    def health():
        return api_response(
            data={"service": "sico-pandas-lab-backend", "readOnlyGuard": guard_result},
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
