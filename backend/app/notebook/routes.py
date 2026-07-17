"""HTTP surface for the free-practice notebook.

All responses go through api_response() so the envelope matches the shared
SICO ApiResponse contract. The worker lifecycle is delegated entirely to the
WorkerManager stored on the Flask app.
"""
from flask import Blueprint, current_app, request

from app.data_access.excel_loader import load_excel_dataframe
from app.utils.api_response import api_response

notebook_bp = Blueprint("notebook", __name__, url_prefix="/api/notebook")

SESSION_HEADER = "X-Session-Id"


def _session_id():
    """Each browser tab supplies its own opaque id; no auth in the MVP."""
    return request.headers.get(SESSION_HEADER) or "anonymous"


def _manager():
    return current_app.config["WORKER_MANAGER"]


@notebook_bp.post("/execute")
def execute_cell():
    payload = request.get_json(silent=True) or {}
    code = payload.get("code", "")
    if not isinstance(code, str) or not code.strip():
        return api_response(
            message="No hay código para ejecutar.", success=False, status=400
        )
    result = _manager().execute(_session_id(), code)
    return api_response(data=result, message="ejecutado")


@notebook_bp.post("/restart")
def restart_session():
    _manager().restart(_session_id())
    return api_response(message="Sesión reiniciada. Empiezas con un notebook limpio.")


@notebook_bp.post("/upload-excel")
def upload_excel():
    if "file" not in request.files:
        return api_response(
            message="No se recibió ningún archivo.", success=False, status=400
        )
    file = request.files["file"]
    var_name = (request.form.get("variable") or "df").strip() or "df"
    try:
        df = load_excel_dataframe(file)
    except ValueError as exc:
        return api_response(message=str(exc), success=False, status=400)

    _manager().bind(_session_id(), var_name, df)
    return api_response(
        data={
            "variable": var_name,
            "rows": int(df.shape[0]),
            "columns": list(map(str, df.columns)),
        },
        message=f"Excel cargado como '{var_name}' ({df.shape[0]} filas).",
    )
