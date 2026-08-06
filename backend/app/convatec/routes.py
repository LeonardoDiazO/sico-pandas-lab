"""HTTP surface for the Convatec assignment + illustrative-commission module.

Demo/pilot scope only (PRD decision 2026-08-05): runs against the same
internal, unauthenticated access model sico-pandas-lab already has today.
The external-access NFR (PRD S5.1) is explicitly deferred to a future
architecture pass, not implemented here.
"""
import math
from datetime import date

from flask import Blueprint, current_app, request, send_file

from app.convatec.column_aliases import normalize_columns
from app.convatec.export import build_output_excel, preview_rows
from app.convatec.master_tables import MasterTablesError, load_master_tables
from app.convatec.patient_columns import drop_patient_columns
from app.convatec.pipeline import calcular_comision_ilustrativa, procesar_ciclo
from app.convatec.session_store import ConvatecSessionStore
from app.data_access.excel_loader import load_excel_dataframe
from app.utils.api_response import api_response

convatec_bp = Blueprint("convatec", __name__, url_prefix="/api/convatec")

SESSION_HEADER = "X-Session-Id"
VENTAS_TIPOS = ("productos", "servicios", "envios-nacionales")
_TIPO_TO_KEY = {"productos": "productos", "servicios": "servicios", "envios-nacionales": "envios_nacionales"}


def _session_id():
    return request.headers.get(SESSION_HEADER) or "anonymous"


def _store() -> ConvatecSessionStore:
    return current_app.config["CONVATEC_SESSION_STORE"]


def _valid_mes(mes) -> bool:
    return isinstance(mes, int) and not isinstance(mes, bool) and 1 <= mes <= 12


def _valid_numero(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@convatec_bp.post("/tablas-maestras")
def upload_master_tables():
    """Story 1.1 (FR-3): replace the whole master-tables set for this session."""
    if "file" not in request.files:
        return api_response(message="No se recibió ningún archivo.", success=False, status=400)
    try:
        tables = load_master_tables(request.files["file"])
    except MasterTablesError as exc:
        return api_response(message=str(exc), success=False, status=400)

    _store().set_master_tables(
        _session_id(), tables["PRODUCTO"], tables["REPRESENTANTES"], tables["CONVENIOS"]
    )
    return api_response(
        data={
            "productoRows": int(tables["PRODUCTO"].shape[0]),
            "representantesRows": int(tables["REPRESENTANTES"].shape[0]),
            "conveniosRows": int(tables["CONVENIOS"].shape[0]),
        },
        message="Tablas maestras cargadas. Reemplazan cualquier versión anterior.",
    )


@convatec_bp.post("/ventas/<tipo>")
def upload_ventas(tipo):
    """Story 1.1 (FR-1, FR-2): upload one sales source. PHI columns are
    dropped for every tipo, not only productos/servicios -- envios-nacionales
    is not expected to carry patient data, but NFR-2 is non-negotiable, so
    this never trusts that assumption blindly (found in code review)."""
    if tipo not in VENTAS_TIPOS:
        return api_response(
            message=f"Tipo de insumo desconocido: {tipo}.", success=False, status=400
        )
    if "file" not in request.files:
        return api_response(message="No se recibió ningún archivo.", success=False, status=400)

    try:
        df = load_excel_dataframe(request.files["file"])
    except ValueError as exc:
        return api_response(message=str(exc), success=False, status=400)

    df = normalize_columns(df)
    df = drop_patient_columns(df)

    _store().set_ventas(_session_id(), _TIPO_TO_KEY[tipo], df)
    return api_response(
        data={"tipo": tipo, "rows": int(df.shape[0]), "columns": list(map(str, df.columns))},
        message=f"{tipo} cargado ({df.shape[0]} filas).",
    )


@convatec_bp.post("/procesar")
def procesar_ciclo_endpoint():
    """Stories 1.2-1.4 (FR-4 a FR-11): run the full assignment pipeline for this session."""
    session_id = _session_id()
    store = _store()
    if not store.has_master_tables(session_id):
        return api_response(
            message="Primero sube las tablas maestras.", success=False, status=400
        )

    payload = request.get_json(silent=True) or {}
    mes = payload.get("mes", date.today().month)
    if not _valid_mes(mes):
        return api_response(message="El mes debe ser un número entero entre 1 y 12.", success=False, status=400)

    producto_table, representantes_table, convenios_table = store.master_tables(session_id)
    try:
        resultado = procesar_ciclo(
            productos=store.get_ventas(session_id, "productos"),
            servicios=store.get_ventas(session_id, "servicios"),
            envios_nacionales=store.get_ventas(session_id, "envios_nacionales"),
            producto_table=producto_table,
            representantes_table=representantes_table,
            convenios_table=convenios_table,
            mes=mes,
        )
    except (ValueError, KeyError) as exc:
        return api_response(message=f"No se pudo procesar el ciclo: {exc}", success=False, status=400)

    store.set_resultado(session_id, resultado)
    total = int(resultado.shape[0])
    marcadas = int(resultado["Motivo_Excepcion"].notna().sum())
    return api_response(
        data={
            "totalLineas": total,
            "lineasMarcadas": marcadas,
            "motivos": resultado["Motivo_Excepcion"].value_counts(dropna=True).to_dict(),
        },
        message=f"Ciclo procesado: {total} líneas, {marcadas} marcadas para revisión.",
    )


@convatec_bp.post("/comision-ilustrativa")
def comision_ilustrativa():
    """Story 2.1 (FR-12): NOT an official commission -- an example split by Sede."""
    session_id = _session_id()
    resultado = _store().get_resultado(session_id)
    if resultado is None:
        return api_response(
            message="Primero procesa un ciclo antes de calcular la comisión ilustrativa.",
            success=False,
            status=400,
        )

    payload = request.get_json(silent=True) or {}
    valor_referencia = payload.get("valorReferencia")
    if not _valid_numero(valor_referencia):
        return api_response(
            message="valorReferencia debe ser un número finito.", success=False, status=400
        )

    con_comision = calcular_comision_ilustrativa(resultado, float(valor_referencia))
    _store().set_resultado(session_id, con_comision)
    return api_response(
        data={"valorReferencia": valor_referencia, "esOficial": False},
        message="Comisión ilustrativa calculada — valor de ejemplo, no oficial.",
    )


@convatec_bp.get("/resultado-preview")
def resultado_preview():
    """Lets the UI show the exact table that /descargar would produce
    (same columns/labels) before committing to the download -- useful to
    eyeball the result on a large cycle before waiting for the full export."""
    resultado = _store().get_resultado(_session_id())
    if resultado is None:
        return api_response(
            message="No hay ningún ciclo procesado para previsualizar.", success=False, status=400
        )

    limit_raw = request.args.get("limit", "50")
    try:
        limit = int(limit_raw)
    except ValueError:
        return api_response(message="limit debe ser un número entero.", success=False, status=400)
    if limit <= 0 or limit > 500:
        return api_response(message="limit debe estar entre 1 y 500.", success=False, status=400)

    return api_response(data=preview_rows(resultado, limit), message="Vista previa del resultado.")


@convatec_bp.get("/descargar")
def descargar_resultado():
    """Story 1.5 / 2.2 (FR-13): same file, plus Comision_Ilustrativa only when it was computed."""
    resultado = _store().get_resultado(_session_id())
    if resultado is None:
        return api_response(
            message="No hay ningún ciclo procesado para descargar.", success=False, status=400
        )

    try:
        buf = build_output_excel(resultado)
    except Exception as exc:  # noqa: BLE001 - never 500 a user-facing download
        return api_response(
            message=f"No se pudo generar el Excel de salida: {exc}", success=False, status=400
        )

    return send_file(
        buf,
        as_attachment=True,
        download_name="convatec_asignacion.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@convatec_bp.post("/reiniciar")
def reiniciar_sesion():
    """Matches the notebook module's `restart` convention -- lets a user
    clear a wrong maestro/ciclo upload without a Flask process restart
    (missing endpoint found in code review)."""
    _store().reset(_session_id())
    return api_response(message="Sesión de Convatec reiniciada.")
