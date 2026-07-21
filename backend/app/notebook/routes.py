"""HTTP surface for the free-practice notebook.

All responses go through api_response() so the envelope matches the shared
SICO ApiResponse contract. The worker lifecycle is delegated entirely to the
WorkerManager stored on the Flask app.
"""
from flask import Blueprint, current_app, request

from app.data_access.excel_profiler import profile_excel
from app.notebook.chart_builder import (
    CHART_TYPES,
    HIGH_CARDINALITY_THRESHOLD,
    build_cardinality_check_code,
    build_chart_code,
    needs_cardinality_check,
)
from app.utils.api_response import api_response

notebook_bp = Blueprint("notebook", __name__, url_prefix="/api/notebook")

SESSION_HEADER = "X-Session-Id"


def _session_id():
    """Each browser tab supplies its own opaque id; no auth in the MVP."""
    return request.headers.get(SESSION_HEADER) or "anonymous"


def _manager():
    return current_app.config["WORKER_MANAGER"]


def _serialize_profile(profile):
    """snake_case internals -> camelCase at the API edge (ApiResponse contract)."""
    return {
        "verdict": profile["verdict"],
        "headerRowIndex": profile["header_row_index"],
        "columns": profile["columns"],
        "detail": profile["detail"],
    }


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
        profile = profile_excel(file)
    except ValueError as exc:
        return api_response(message=str(exc), success=False, status=400)

    df = profile["dataframe"]
    verdict = profile["verdict"]
    bound = False

    # A new upload always supersedes whatever this session had pending before,
    # regardless of this upload's own verdict -- otherwise a stale staged
    # DataFrame from an earlier "usable_con_limpieza" attempt could still be
    # bound later by a delayed/duplicate confirm-excel-cleanup call.
    _manager().discard_pending_upload(_session_id())

    if verdict == "usable":
        _manager().bind(_session_id(), var_name, df)
        bound = True
    elif verdict == "usable_con_limpieza":
        _manager().stage_pending_upload(_session_id(), var_name, df, profile)

    rows = int(df.shape[0]) if df is not None else 0
    columns = list(map(str, df.columns)) if df is not None else []

    return api_response(
        data={
            "variable": var_name,
            "rows": rows,
            "columns": columns,
            "profile": _serialize_profile(profile),
            "bound": bound,
        },
        message=(
            f"Excel cargado como '{var_name}' ({rows} filas)."
            if bound
            else profile["detail"]
        ),
    )


@notebook_bp.post("/confirm-excel-cleanup")
def confirm_excel_cleanup():
    pending = _manager().pop_pending_upload(_session_id())
    if pending is None:
        return api_response(
            message="No hay ninguna limpieza pendiente por confirmar.", success=False, status=400
        )
    variable, df, profile = pending
    try:
        _manager().bind(_session_id(), variable, df)
    except TimeoutError:
        # Don't lose the cleaned DataFrame just because the worker was briefly
        # unresponsive -- restage it so the user can retry confirm without
        # re-uploading and redoing the cleanup from scratch.
        _manager().stage_pending_upload(_session_id(), variable, df, profile)
        return api_response(
            message="La sesión no respondió a tiempo. Intenta confirmar de nuevo.",
            success=False,
            status=504,
        )
    return api_response(
        data={
            "variable": variable,
            "rows": int(df.shape[0]),
            "columns": list(map(str, df.columns)),
            # Epic 5 needs the column-type profile to populate its selectors
            # for any Excel that went through this confirm-cleanup path, not
            # just the immediate-bind "usable" path upload-excel handles.
            "profile": _serialize_profile(profile),
            "bound": True,
        },
        message=f"Excel limpio cargado como '{variable}' ({df.shape[0]} filas).",
    )


@notebook_bp.post("/cancel-excel-cleanup")
def cancel_excel_cleanup():
    _manager().discard_pending_upload(_session_id())
    return api_response(message="Carga cancelada. Puedes subir otro archivo.")


def _empty_cell_result():
    """A CellResult with nothing in it - used when a cardinality warning
    blocks generation before any chart code ran."""
    return {"stdout": "", "result_html": None, "result_text": None, "image_base64": None, "error": None}


def _chart_response_data(result, needs_confirmation=False, cardinality_warning=None):
    """Every /generate-chart response carries the same shape (CellResult plus
    these two fields), whether or not a cardinality warning fired -- one
    stable shape, a boolean discriminant, same pattern as `bound` on the
    upload-excel response (Story 4.2)."""
    return {**result, "needsConfirmation": needs_confirmation, "cardinalityWarning": cardinality_warning}


@notebook_bp.post("/generate-chart")
def generate_chart():
    payload = request.get_json(silent=True) or {}
    variable = payload.get("variable")
    column = payload.get("column")
    value_column = payload.get("valueColumn")
    chart_type = payload.get("chartType")
    force = payload.get("force") is True

    if not isinstance(variable, str) or not variable.strip():
        return api_response(message="Falta la variable del DataFrame.", success=False, status=400)
    if chart_type not in CHART_TYPES:
        return api_response(message="Tipo de gráfica no reconocido.", success=False, status=400)
    if chart_type != "histograma" and not column:
        return api_response(message="Falta elegir una columna para agrupar.", success=False, status=400)
    if chart_type == "histograma" and not value_column:
        return api_response(
            message="Falta elegir una columna de valor para el histograma.", success=False, status=400
        )

    if needs_cardinality_check(chart_type) and not force:
        check_result = _manager().execute(_session_id(), build_cardinality_check_code(variable, column))
        if check_result.get("error"):
            return api_response(
                data=_chart_response_data(check_result), message="No se pudo generar la gráfica."
            )
        try:
            unique_count = int(check_result["result_text"])
        except (TypeError, ValueError):
            # nunique() on a Series always returns a plain int, so this should
            # be unreachable - but result_text is a display-string channel
            # (execution.py's repr()), not a typed contract, so guard it
            # rather than let a surprise shape 500 the request.
            return api_response(
                message="No se pudo calcular la cardinalidad de la columna.", success=False, status=502
            )
        if unique_count > HIGH_CARDINALITY_THRESHOLD:
            empty_result = _empty_cell_result()
            warning = {
                "column": column,
                "uniqueCount": unique_count,
                "threshold": HIGH_CARDINALITY_THRESHOLD,
                "suggestion": (
                    'Agrupa esta columna en "top N + otros" antes de graficar, '
                    "o elige otra columna con menos valores distintos."
                ),
            }
            return api_response(
                data=_chart_response_data(empty_result, needs_confirmation=True, cardinality_warning=warning),
                message=f"'{column}' tiene {unique_count} valores distintos — la gráfica podría no verse bien.",
            )

    code = build_chart_code(chart_type, variable, column, value_column)
    result = _manager().execute(_session_id(), code)
    return api_response(
        data=_chart_response_data(result),
        message="Gráfica generada." if not result.get("error") else "No se pudo generar la gráfica.",
    )
