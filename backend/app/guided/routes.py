"""HTTP surface for the guided-learning module.

Serves lesson content and checks challenge attempts. Execution of guided
steps reuses the notebook execute endpoint; only challenge-checking (which
needs to run a verifier against the same live namespace) has its own route.
"""
from flask import Blueprint, current_app, request

from app.guided import content, data_context
from app.guided.challenges import CHALLENGE_TO_LESSON
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
    profile = _manager().get_known_profile(_session_id())
    found = content.get_lesson(lesson_id, learner_profile=profile)
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

    session_id = _session_id()
    lesson_id = CHALLENGE_TO_LESSON.get(challenge_id)
    profile = _manager().get_known_profile(session_id)
    context = data_context.resolve_context(lesson_id, profile) if lesson_id else None

    result = _manager().execute_challenge(session_id, code, challenge_id, context)
    return api_response(data=result, message="Reto revisado.")
