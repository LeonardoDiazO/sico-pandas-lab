"""HTTP surface for read-only access to the sico data.

Loading a table binds the resulting DataFrame straight into the caller's
notebook session under a predictable variable name, so the user can
immediately work with it in their cells. Combining tables is intentionally
NOT done here — the user does that with pd.merge() on the DataFrames they
load, which is the actual pandas skill this tool exists to practice.
"""
import re

from flask import Blueprint, current_app, request

from app.data_access import sico_client
from app.utils.api_response import api_response

data_bp = Blueprint("data_access", __name__, url_prefix="/api/data")

SESSION_HEADER = "X-Session-Id"

_NON_IDENTIFIER = re.compile(r"\W")


def _session_id():
    return request.headers.get(SESSION_HEADER) or "anonymous"


def _manager():
    return current_app.config["WORKER_MANAGER"]


def _variable_name(requested, table):
    raw = requested or f"df_{table}"
    safe = _NON_IDENTIFIER.sub("_", raw)
    if safe[:1].isdigit():
        safe = f"df_{safe}"
    return safe


@data_bp.get("/tables")
def list_tables():
    try:
        tables = sico_client.list_tables()
    except sico_client.SicoNotConfigured:
        return api_response(
            data={"schema": sico_client.SCHEMA, "tables": [], "configured": False},
            message="La conexión a la base de datos de sico no está configurada.",
        )
    except Exception:  # noqa: BLE001 - surface connection issues cleanly, no secrets
        return api_response(
            data={"schema": sico_client.SCHEMA, "tables": [], "configured": True},
            message="No se pudo consultar la lista de tablas (revisa la conexión).",
            success=False,
            status=502,
        )
    return api_response(
        data={"schema": sico_client.SCHEMA, "tables": tables, "configured": True},
        message=f"{len(tables)} tablas disponibles en el esquema {sico_client.SCHEMA}.",
    )


@data_bp.post("/load-table")
def load_table():
    payload = request.get_json(silent=True) or {}
    table = payload.get("table")
    if not table:
        return api_response(message="Falta el nombre de la tabla.", success=False, status=400)
    variable = _variable_name(payload.get("variable"), table)

    try:
        df = sico_client.load_table(table)
    except (ValueError, sico_client.SicoNotConfigured) as exc:
        return api_response(message=str(exc), success=False, status=400)
    except Exception:  # noqa: BLE001 - surface connection issues cleanly, no secrets
        return api_response(message="No se pudo consultar la base de datos de sico.", success=False, status=502)

    _manager().bind(_session_id(), variable, df)
    return api_response(
        data={"variable": variable, "rows": int(df.shape[0]), "columns": list(map(str, df.columns))},
        message=f"Tabla '{table}' cargada como '{variable}' ({df.shape[0]} filas). Combínala con otras usando pd.merge().",
    )
