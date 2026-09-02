"""Classifies each column of a profiled Excel into a semantic role -
dimension/metrica/fecha/identificador/descartar - so the no-code screen can
suggest a starting point instead of asking the user to already know which
column is "the dimension" and which is "the metric" (the actual complaint
this module answers: today's manual selectors work, but only for someone who
already understands their own data structurally).

Same pattern as nl_chart_interpreter.py (Epic 6), reused deliberately rather
than reinvented: `google.genai` structured output (a JSON Schema constrains
the model's answer via `enum`, so it can literally only pick one of the 5
role names - never invent a new one), same MODEL, same lazy client, same
InterpreterUnavailableError contract.

Security note (NFR10/NFR11, same guarantee as nl_chart_interpreter.py): this
module never builds or executes pandas code, and the model only ever sees
column metadata (name/type/a handful of sample values/uniqueRatio) - never
the DataFrame's rows. excel_profiler.py's _column_stats() already caps
sampleValues at 5 entries per column for exactly this reason.

Design note: `_fallback_classification()` isn't only a degraded mode for
when GEMINI_API_KEY is missing - it's also the reference rules the model is
instructed to follow, so a misclassification is still "the same idea,
possibly refined by seeing sample values" rather than a black box. Every
column always gets a role (the model is never trusted alone): the fallback
runs FIRST, and the LLM result (when available) replaces it only for the
columns the model actually returned a valid answer for.
"""
import json
import os

from google import genai
from google.genai import errors, types

from app.data_access.excel_profiler import TYPE_CATEGORICA, TYPE_DESCARTABLE, TYPE_FECHA, TYPE_NUMERICA

MODEL = "gemini-flash-latest"

ROLE_DIMENSION = "dimension"
ROLE_METRICA = "metrica"
ROLE_FECHA = "fecha"
ROLE_IDENTIFICADOR = "identificador"
ROLE_DESCARTAR = "descartar"

ROLES = (ROLE_DIMENSION, ROLE_METRICA, ROLE_FECHA, ROLE_IDENTIFICADOR, ROLE_DESCARTAR)

# A categorica column whose values are almost all distinct behaves like an
# identifier (invoice number, NIT), not something worth grouping by - same
# spirit as chart_builder.py's HIGH_CARDINALITY_THRESHOLD, but expressed as a
# ratio here since it applies before any row count is known.
_IDENTIFIER_UNIQUE_RATIO = 0.9

_client_singleton = None


class InterpreterUnavailableError(Exception):
    """El clasificador no está disponible (sin API key, error del proveedor, etc.)."""


def _default_client():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client_singleton


def _fallback_role(column):
    """Deterministic rule for one column - see module docstring: this is not
    only the no-AI fallback, it's the reference the LLM prompt itself states
    as ground truth."""
    if column["type"] == TYPE_DESCARTABLE:
        return ROLE_DESCARTAR
    if column["type"] == TYPE_FECHA:
        return ROLE_FECHA
    if column["type"] == TYPE_NUMERICA:
        return ROLE_METRICA
    if column["type"] == TYPE_CATEGORICA:
        if column.get("uniqueRatio", 0) >= _IDENTIFIER_UNIQUE_RATIO:
            return ROLE_IDENTIFICADOR
        return ROLE_DIMENSION
    return ROLE_DESCARTAR


def _fallback_classification(columns):
    return [{"name": c["name"], "role": _fallback_role(c)} for c in columns]


_SYSTEM_PROMPT = (
    "Clasificas cada columna de un archivo subido por un usuario de negocio en "
    "uno de 5 roles: 'dimension' (categoría para agrupar, ej. vendedor, ciudad, "
    "producto), 'metrica' (número que se suma/promedia, ej. ventas, cantidad), "
    "'fecha' (columna temporal), 'identificador' (código único por fila que no "
    "tiene sentido agrupar ni sumar, ej. número de factura, NIT, cédula), o "
    "'descartar' (columna vacía o sin información útil). Reglas de referencia: "
    "tipo 'fecha' del perfil -> rol 'fecha'; tipo 'numerica' -> 'metrica'; tipo "
    "'categorica' con uniqueRatio muy alto (casi todos los valores distintos) -> "
    "'identificador'; tipo 'categorica' con uniqueRatio bajo -> 'dimension'; "
    "tipo 'descartable' -> 'descartar'. Usa los valores de muestra (sampleValues) "
    "solo para refinar casos ambiguos que el tipo/uniqueRatio por sí solos no "
    "resuelven bien - nunca contradigas el tipo del perfil sin una razón clara "
    "visible en las muestras. Nunca inventes un nombre de columna que no esté en "
    "la lista dada."
)


def _build_schema(columns):
    names = [c["name"] for c in columns]
    return {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": names},
                        "role": {"type": "string", "enum": list(ROLES)},
                    },
                    "required": ["name", "role"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["classifications"],
        "additionalProperties": False,
    }


def _llm_input_columns(columns):
    """Strips the profile down to exactly what the model needs to decide a
    role - name/type/uniqueRatio/sampleValues - never the DataFrame, never
    nullRatio (irrelevant to role, would just be noise in the prompt)."""
    return [
        {
            "name": c["name"],
            "type": c["type"],
            "uniqueRatio": c.get("uniqueRatio"),
            "sampleValues": c.get("sampleValues", []),
        }
        for c in columns
    ]


def classify_columns(columns, client=None):
    """Returns {"classifications": [{"name", "role"}, ...], "usedAssistant": bool}.

    Every column always gets a role - starts from the deterministic fallback,
    then overlays the LLM's answer for whichever columns it validly resolved.
    Never raises for an unavailable/misbehaving LLM (falls back silently and
    reports usedAssistant=False) - unlike nl_chart_interpreter.py's
    interpret_chart_request(), classification is a required step in the
    no-code flow, not an optional assistant a user opted into asking.
    """
    fallback = _fallback_classification(columns)
    if not columns:
        return {"classifications": fallback, "usedAssistant": False}

    if client is None:
        if not os.environ.get("GEMINI_API_KEY"):
            return {"classifications": fallback, "usedAssistant": False}
        client = _default_client()

    schema = _build_schema(columns)
    user_content = f"Columnas: {json.dumps(_llm_input_columns(columns), ensure_ascii=False)}"

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            ),
        )
        text = response.text
        if not text:
            return {"classifications": fallback, "usedAssistant": False}
        parsed = json.loads(text)
    except (errors.APIError, TypeError, ValueError):
        return {"classifications": fallback, "usedAssistant": False}

    llm_roles = {}
    valid_names = {c["name"] for c in columns}
    for entry in parsed.get("classifications", []) if isinstance(parsed, dict) else []:
        if not isinstance(entry, dict):
            continue
        name, role = entry.get("name"), entry.get("role")
        if name in valid_names and role in ROLES:
            llm_roles[name] = role

    if not llm_roles:
        return {"classifications": fallback, "usedAssistant": False}

    merged = [{"name": c["name"], "role": llm_roles.get(c["name"], _fallback_role(c))} for c in columns]
    return {"classifications": merged, "usedAssistant": True}
