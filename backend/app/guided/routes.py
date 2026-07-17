"""HTTP surface for the guided-learning module.

Serves lesson content and checks challenge attempts. Execution of guided
steps reuses the notebook execute endpoint; only challenge-checking (which
needs to run a verifier against the same live namespace) has its own route.
"""
from flask import Blueprint, current_app, request

from app.guided import content
from app.utils.api_response import api_response

guided_bp = Blueprint("guided", __name__, url_prefix="/api/guided")

SESSION_HEADER = "X-Session-Id"


def _session_id():
    return request.headers.get(SESSION_HEADER) or "anonymous"


def _manager():
    return current_app.config["WORKER_MANAGER"]


@guided_bp.get("/lessons")
def lessons():
    return api_response(data={"lessons": content.list_lessons()}, message="Lecciones disponibles.")


@guided_bp.get("/lessons/<lesson_id>")
def lesson(lesson_id):
    found = content.get_lesson(lesson_id)
    if found is None:
        return api_response(message="Lección no encontrada.", success=False, status=404)
    return api_response(data=found, message="Lección cargada.")


@guided_bp.post("/challenge/check")
def check_challenge():
    payload = request.get_json(silent=True) or {}
    code = payload.get("code", "")
    challenge_id = payload.get("challenge_id", "")
    if not isinstance(code, str) or not code.strip():
        return api_response(message="No hay código para revisar.", success=False, status=400)
    if not isinstance(challenge_id, str) or not challenge_id:
        return api_response(message="Falta el identificador del reto.", success=False, status=400)

    result = _manager().execute_challenge(_session_id(), code, challenge_id)
    return api_response(data=result, message="Reto revisado.")
