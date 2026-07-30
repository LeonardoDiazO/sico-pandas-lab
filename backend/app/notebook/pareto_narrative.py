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

Security note (NFR11 - RELAXED here, by explicit user choice): earlier
versions of this module sent only aggregate numbers (crossing counts, one
top row/group). The user asked why not send everything for a more complete
analysis ("por qué no manda todo... para que gemini pueda sacar un analisis
más completo") and explicitly chose "Todo (los 88 grupos y las 171 filas
completos)" over a top-5/10 subset. This module now also receives the full
row_records/group_records lists - the same rows/groups already rendered on
screen in "Ordenar tabla"/"Resumen y porcentaje por columna" (the frontend
projects each row down to only the grouping column(s) + value/percentage/
marker columns before sending - see no-code-table.component.ts's
buildNarrativeStats() - but that projection is a token/noise optimization,
not a confidentiality boundary: every column that IS sent is real,
identifiable client/invoice data, by the user's own informed choice, since
they control what's in the uploaded Excel file and are responsible for
configuring GEMINI_API_KEY themselves).

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
    "técnico, en español. Se te dan dos vistas COMPLETAS y ya calculadas de "
    "un análisis 80/20 (Pareto) sobre el mismo archivo: 'filas' es la lista "
    "completa de cada fila individual (ej. cada factura), ordenada de mayor "
    "a menor valor; 'grupos' es la lista completa de cada grupo (ej. cada "
    "cliente), también ordenada de mayor a menor valor total. Ambas listas "
    "incluyen su(s) columna(s) de agrupación, así que puedes correlacionar "
    "una fila individual con su grupo cruzando ese valor compartido - por "
    "ejemplo, para saber si el grupo de mayor valor realmente reúne varias "
    "de las filas de mayor valor individual, o si en cambio depende de "
    "muchas filas pequeñas. 'filas_resumen'/'grupos_resumen' traen el total "
    "de filas/grupos y cuántas de ellas concentran el 80% del total. Usa "
    "ÚNICAMENTE estos datos - nunca inventes cifras, nombres o columnas "
    "adicionales, y no asumas nada sobre filas o grupos que no aparezcan en "
    "las listas dadas (pueden venir recortadas por límites de la "
    "aplicación). Cualquier afirmación sobre CÓMO se compone un grupo (si "
    "depende de pocas filas grandes o de muchas filas pequeñas) debe poder "
    "verificarse cruzando 'grupos' contra 'filas' - cita los valores "
    "concretos que lo respaldan. Escribe 2-4 frases. Revisa toda la lista "
    "de 'grupos' (no solo el primero) por si el nombre de alguno parece una "
    "categoría genérica o un comprador anónimo (ej. 'consumidor final', "
    "'varios', 'n/a', 'público general', 'mostrador', 'cliente ocasional') "
    "en vez de un cliente real e identificable, y menciona esa posibilidad "
    "explícitamente como advertencia para no sobre-interpretarlo como un "
    "cliente valioso. Cierra con una conclusión de negocio de una frase, "
    "lista para citar directamente. No uses markdown ni viñetas, solo texto "
    "corrido."
)


def build_stats_payload(
    row_stats,
    row_records,
    group_stats,
    group_records,
    value_column_row,
    value_column_group,
    group_columns_label,
):
    """Assembles the exact payload sent to the LLM - the crossing summary
    stats plus the full row/group record lists (user's explicit "Todo (los
    88 grupos y las 171 filas completos)" choice), all of it already
    computed/rendered by the frontend from its own result_records/stdout
    (see no-code-table.component.ts), never derived fresh from raw data by
    this module."""
    return {
        "columna_valor_fila": value_column_row,
        "filas_resumen": row_stats,
        "filas": row_records,
        "columna_agrupacion": group_columns_label,
        "columna_valor_grupo": value_column_group,
        "grupos_resumen": group_stats,
        "grupos": group_records,
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
