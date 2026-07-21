"""Translates a natural-language chart request into a selection from the
closed set Epic 5 already validates (Story 6.1).

Security note (NFR10, non-negotiable): this module never builds or executes
pandas code - its only output is a selection of {column, valueColumn,
chartType} drawn from options the caller supplies, or "not resolved". Two
layers of defense, neither sufficient alone:
  1. The JSON Schema sent to the LLM constrains column/chart-type names via
     `enum`, built per-request from the actual columns of this Excel - the
     model literally cannot invent a name that isn't in the list.
  2. This module re-validates the LLM's answer in Python against the same
     compatibility rules the frontend already applies (see
     no-code-chart.component.ts's chartTypeOptions) before returning it -
     never trust the schema alone.

Security note (NFR11): only column metadata (name/type) plus the user's
question text are ever sent to the LLM - never DataFrame content.
"""
import json
import os

import anthropic

from app.notebook.chart_builder import CHART_TYPES

MODEL = "claude-opus-4-8"

_GROUPABLE_TYPES = {"categorica", "fecha"}
_NUMERIC_TYPE = "numerica"

# Which field must resolve to which column type for a given chart type - the
# backend copy of the same compatibility rules the frontend's
# no-code-chart.component.ts chartTypeOptions getter applies for the manual
# selectors. Kept as one small table (rather than a chain of if-statements)
# so a future chart type is one row to add, not a new branch to hand-write.
_CHART_TYPE_REQUIREMENTS = {
    "torta": ("column", "categorica"),
    "barras": ("column", "categorica"),
    "linea": ("column", "fecha"),
    "histograma": ("valueColumn", "numerica"),
}

_client_singleton = None

_SYSTEM_PROMPT = (
    "Traduces una pregunta de negocio en español a una selección dentro de un "
    "menú cerrado de opciones de gráfica. Nunca inventes un nombre de columna "
    "que no esté en la lista de columnas dada - elige exclusivamente entre los "
    "valores permitidos por el schema. Si la pregunta no se puede resolver con "
    "una sola combinación de columna + tipo de gráfica del menú dado (por "
    "ejemplo, pide comparar dos periodos o cruzar varias condiciones), responde "
    "con resolved=false y explica brevemente por qué en 'reason', sugiriendo "
    "usar los selectores manuales."
)

_NOT_RESOLVED = {
    "resolved": False,
    "column": None,
    "valueColumn": None,
    "chartType": None,
    "reason": (
        "No encontré una combinación de columna y tipo de gráfica que resuelva "
        "esa pregunta. Prueba con los selectores manuales."
    ),
}


class InterpreterUnavailableError(Exception):
    """El asistente no está disponible (sin API key, error del proveedor, etc.)."""


def _nullable_enum(names):
    if not names:
        return {"type": "null"}
    return {"anyOf": [{"type": "string", "enum": names}, {"type": "null"}]}


def build_interpretation_schema(columns):
    groupable_names = [c["name"] for c in columns if c["type"] in _GROUPABLE_TYPES]
    numeric_names = [c["name"] for c in columns if c["type"] == _NUMERIC_TYPE]
    return {
        "type": "object",
        "properties": {
            "resolved": {"type": "boolean"},
            "column": _nullable_enum(groupable_names),
            "valueColumn": _nullable_enum(numeric_names),
            "chartType": _nullable_enum(sorted(CHART_TYPES)),
            "reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        "required": ["resolved", "column", "valueColumn", "chartType", "reason"],
        "additionalProperties": False,
    }


def _default_client():
    """A single shared SDK client, constructed lazily on first use (not one
    new client - and its own httpx connection pool - per assistant question).
    """
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = anthropic.Anthropic()
    return _client_singleton


def interpret_chart_request(question, columns, client=None):
    """Returns a dict with the same shape as _NOT_RESOLVED, or a resolved
    selection - never raises for a "couldn't figure it out" case (AC2), only
    for actual unavailability (InterpreterUnavailableError) or a malformed
    call (ValueError)."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question no puede estar vacío")

    if client is None:
        # The SDK does NOT raise anthropic.AnthropicError for a missing key -
        # anthropic.Anthropic() constructs successfully either way, and the
        # first request instead fails deep inside client.messages.create()
        # with a bare TypeError that `except anthropic.AnthropicError` below
        # does not catch. Check explicitly so this degrades to the documented
        # "asistente no disponible" message instead of an uncaught 500.
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise InterpreterUnavailableError(
                "El asistente no está disponible en este momento."
            )
        client = _default_client()

    schema = build_interpretation_schema(columns)
    user_content = (
        f"Columnas disponibles: {json.dumps(columns, ensure_ascii=False)}\n"
        f"Pregunta del usuario: {question}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AnthropicError as exc:
        raise InterpreterUnavailableError(
            "El asistente no está disponible en este momento."
        ) from exc

    if getattr(response, "stop_reason", None) == "refusal":
        return dict(_NOT_RESOLVED)

    text_block = next(
        (b for b in response.content if getattr(b, "type", None) == "text"), None
    )
    if text_block is None:
        raise InterpreterUnavailableError(
            "El asistente no devolvió una respuesta interpretable."
        )

    try:
        parsed = json.loads(text_block.text)
    except (TypeError, ValueError) as exc:
        raise InterpreterUnavailableError(
            "El asistente no devolvió una respuesta interpretable."
        ) from exc

    return _validate_and_normalize(parsed, columns)


def _validate_and_normalize(parsed, columns):
    if not isinstance(parsed, dict) or not parsed.get("resolved"):
        reason = parsed.get("reason") if isinstance(parsed, dict) else None
        if isinstance(reason, str) and reason.strip():
            return {**_NOT_RESOLVED, "reason": reason}
        return dict(_NOT_RESOLVED)

    column = parsed.get("column")
    value_column = parsed.get("valueColumn")
    chart_type = parsed.get("chartType")
    by_name = {c["name"]: c["type"] for c in columns}

    requirement = _CHART_TYPE_REQUIREMENTS.get(chart_type)
    if requirement is None:
        return dict(_NOT_RESOLVED)
    required_field, required_type = requirement
    required_value = column if required_field == "column" else value_column
    if by_name.get(required_value) != required_type:
        return dict(_NOT_RESOLVED)

    # value_column, when present, must always resolve to a numeric column -
    # even for chart types where it's an optional "sum by" field rather than
    # the chart's own required field (already checked above for histograma,
    # so skip re-checking it there).
    if required_field != "valueColumn" and value_column is not None and by_name.get(value_column) != "numerica":
        return dict(_NOT_RESOLVED)

    return {
        "resolved": True,
        "column": column,
        "valueColumn": value_column,
        "chartType": chart_type,
        "reason": None,
    }
