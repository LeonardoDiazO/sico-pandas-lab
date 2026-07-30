"""Generates a short business-analyst narrative comparing two levels of
80/20 (Pareto) analysis - by individual row (e.g. each invoice) vs by group
(e.g. by client) - once the user has generated both "Ordenar tabla" and
"Resumen y porcentaje por columna" (user feedback: replaces a removed
deterministic/hardcoded text with a real assistant call, "mandandole el
promt adecuado cuando se completen las dos graficas y ahi esperar a que el
responda").

Reuses nl_chart_interpreter.py's Gemini client/error-handling plumbing
(_default_client, InterpreterUnavailableError, MODEL, _BLOCKED_FINISH_REASONS)
rather than duplicating it - same provider, same "not configured/unavailable"
degradation, just a different task (free-form narrative text instead of a
closed-set JSON selection).

Security note (NFR11, same principle as nl_chart_interpreter.py): only
already-computed AGGREGATE numbers travel to the LLM here - total row/group
counts, the 80% crossing point, the top row's and top group's own value and
label. Every one of these is already visible on screen (the tables/charts
already generated it) - nothing new about the underlying data is exposed,
and no raw DataFrame rows ever leave the backend.

Security note (NFR10): this module's only output is TEXT to display - never
code, never a selection that drives further execution. The frontend must
render it as plain interpolated text (not innerHTML) so even a surprising
response can't inject markup - see no-code-table.component.html.
"""
import json
import os

from google.genai import errors, types

from app.notebook.nl_chart_interpreter import (
    _BLOCKED_FINISH_REASONS,
    MODEL,
    InterpreterUnavailableError,
    _default_client,
)

_SYSTEM_PROMPT = (
    "Eres un analista de datos senior explicando un hallazgo a un gerente no "
    "técnico, en español. Se te dan números YA CALCULADOS de dos vistas de un "
    "análisis 80/20 (Pareto) sobre el mismo archivo: una por fila individual "
    "(ej. cada factura) y otra agrupada (ej. por cliente). Usa ÚNICAMENTE los "
    "números que se te dan - nunca inventes cifras, nombres o columnas "
    "adicionales. Escribe 2-4 frases explicando qué significa la diferencia "
    "entre ambas vistas para el negocio. Si el nombre del grupo con mayor "
    "valor (top_grupo_nombre) parece una categoría genérica o un comprador "
    "anónimo (ej. 'consumidor final', 'varios', 'n/a', 'público general', "
    "'mostrador', 'cliente ocasional') en vez de un cliente real e "
    "identificable, menciona esa posibilidad explícitamente como una "
    "advertencia para no sobre-interpretarlo como un cliente valioso. Cierra "
    "con una conclusión de negocio de una frase, lista para citar "
    "directamente. No uses markdown ni viñetas, solo texto corrido."
)


def build_stats_payload(
    row_stats,
    group_stats,
    value_column_row,
    value_column_group,
    group_columns_label,
):
    """Assembles the exact (and only) numbers sent to the LLM - each field
    here is something the frontend already computed from its own
    result_records/stdout (see no-code-table.component.ts), never derived
    fresh from raw data by this module."""
    return {
        "columna_valor_fila": value_column_row,
        "filas": row_stats,
        "columna_agrupacion": group_columns_label,
        "columna_valor_grupo": value_column_group,
        "grupos": group_stats,
    }


def generate_pareto_narrative(stats, client=None):
    """Returns the generated narrative text. Raises InterpreterUnavailableError
    for any "can't produce this right now" case (no API key, provider error,
    blocked/empty response) - same exception type nl_chart_interpreter.py
    already uses, so routes.py handles both the same way."""
    if client is None:
        if not os.environ.get("GEMINI_API_KEY"):
            raise InterpreterUnavailableError("El asistente no está disponible en este momento.")
        client = _default_client()

    user_content = json.dumps(stats, ensure_ascii=False)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                # Free-form prose (not a closed-set selection like
                # nl_chart_interpreter.py) genuinely benefits from the
                # model's default reasoning - e.g. recognizing "consumidor
                # final" as a generic-buyer pattern isn't a lookup, it's
                # judgment - so thinking is left at its default here,
                # unlike that module's MINIMAL override.
            ),
        )
    except errors.APIError as exc:
        raise InterpreterUnavailableError("El asistente no está disponible en este momento.") from exc

    finish_reason = None
    if response.candidates:
        finish_reason = getattr(response.candidates[0], "finish_reason", None)
    if finish_reason in _BLOCKED_FINISH_REASONS:
        raise InterpreterUnavailableError("El asistente no pudo generar un análisis para estos datos.")

    text = response.text
    if not text or not text.strip():
        raise InterpreterUnavailableError("El asistente no devolvió una respuesta interpretable.")

    return text.strip()
