"""Server-side challenge checkers for the guided-learning module.

Each checker runs INSIDE the sandboxed execution worker, straight against the
learner's own namespace, right after their code executes -- the checker
function itself is never sent to the browser, so the answer can't be read
from the network tab.

Checks compare against a value recomputed from the learner's OWN loaded
DataFrame (real sico data, the learner's own uploaded Excel, or the lesson's
synthetic fallback -- whichever is in the namespace) rather than a hardcoded
expected number. That is what lets the same check pass whether the learner
practiced on the real table or the try/except synthetic example -- there is
no fixed "golden answer".

Each checker takes an optional ``context`` (see app.guided.data_context):
{"table_var": str, "roles": {role: column_name}}. It tells the checker which
DataFrame/columns are "in play" for THIS attempt -- resolved once, server
side, from the learner's excel_profiler profile if they uploaded their own
data, or left as None to fall back to each checker's own
_DEFAULT_CONTEXT (the lesson's historic synthetic df_02_movimiento/mov_item/
mov_cantidad/mov_neto names, unchanged from before this parameter existed).
"""

# Historic hardcoded names each checker used before `context` existed --
# kept as the default so a caller that never resolves a context (or a
# session that never uploaded its own Excel) gets exactly the old behavior.
_DEFAULT_CONTEXT_FUNDAMENTOS = {"table_var": "df_02_movimiento", "roles": {"num1": "mov_cantidad"}}
_DEFAULT_CONTEXT_AGRUPAR = {"table_var": "df_02_movimiento", "roles": {"cat": "mov_item", "num2": "mov_neto"}}


def _fail(message):
    return {"passed": False, "message": message}


def _ok(message):
    return {"passed": True, "message": message}


def _check_fundamentos_total(ns, context=None):
    context = context or _DEFAULT_CONTEXT_FUNDAMENTOS
    table_var = context["table_var"]
    qty_col = context["roles"]["num1"]

    if table_var not in ns:
        return _fail(
            f"Necesitas `{table_var}` en esta sesión antes del reto -- "
            "carga la tabla desde el panel de arriba, o corre primero el "
            "paso 1.2 de esta lección (crea el ejemplo de práctica)."
        )
    if "total_cantidad" not in ns:
        return _fail("Aún no existe una variable llamada `total_cantidad`. Guarda tu respuesta con ese nombre exacto.")

    esperado = ns[table_var][qty_col].sum()
    try:
        coincide = abs(float(ns["total_cantidad"]) - float(esperado)) < 1e-6
    except (TypeError, ValueError):
        return _fail("`total_cantidad` debe ser un número (el resultado de sumar una columna).")

    if not coincide:
        return _fail(
            f"`total_cantidad` no coincide con la suma real de la columna `{qty_col}`. "
            f"Pista: `{table_var}['{qty_col}'].sum()`."
        )
    return _ok(f"¡Correcto! Esa es la suma total de {qty_col}.")


def _check_agrupar_total_por_item(ns, context=None):
    import pandas as pd

    context = context or _DEFAULT_CONTEXT_AGRUPAR
    table_var = context["table_var"]
    cat_col = context["roles"]["cat"]
    value_col = context["roles"]["num2"]

    if table_var not in ns:
        return _fail(
            f"Necesitas `{table_var}` en esta sesión antes del reto -- "
            "carga la tabla desde el panel de arriba, o corre primero el paso 3.1 de esta lección."
        )
    if "resultado" not in ns:
        return _fail("Aún no existe una variable llamada `resultado`. Guarda tu respuesta con ese nombre exacto.")

    resultado = ns["resultado"]
    if not isinstance(resultado, pd.Series):
        return _fail(
            "`resultado` debe ser una Series -- el resultado de agrupar por una columna y "
            f"resumir una sola métrica (por ejemplo `.groupby('{cat_col}')['{value_col}'].sum()`)."
        )

    esperado = ns[table_var].groupby(cat_col)[value_col].sum().sort_values(ascending=False)
    try:
        coincide_valores = resultado.sort_index().equals(esperado.sort_index())
    except Exception:
        return _fail(f"No se pudo comparar tu resultado -- revisa que agrupaste por '{cat_col}' y sumaste '{value_col}'.")

    if not coincide_valores:
        return _fail(
            f"Los valores no coinciden con agrupar `{table_var}` por '{cat_col}' y sumar "
            f"'{value_col}'. Revisa la columna y la operación que usaste."
        )

    valores = list(resultado.values)
    if valores != sorted(valores, reverse=True):
        return _fail(
            "Los valores agrupados están bien, pero falta ordenar de mayor a menor -- "
            "agrega `.sort_values(ascending=False)`."
        )
    return _ok("¡Perfecto! Agrupaste, sumaste y ordenaste correctamente.")


CHALLENGES = {
    "01-fundamentos:reto-1": {
        "prompt": (
            "Reto: usando `df_02_movimiento` (carga la tabla real desde el panel arriba, o "
            "corre el paso 1.2 si aún no lo has hecho), calcula la suma total de la columna "
            "`mov_cantidad` y guárdala en una variable llamada exactamente `total_cantidad`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `total_cantidad`\n",
        "check": _check_fundamentos_total,
    },
    "03-agrupar:reto-1": {
        "prompt": (
            "Reto: usando `df_02_movimiento`, agrupa por `mov_item`, suma `mov_neto`, ordena "
            "de mayor a menor, y guarda el resultado en una variable llamada exactamente "
            "`resultado`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `resultado`\n",
        "check": _check_agrupar_total_por_item,
    },
}


# challenge_id -> the lesson that defines it (content.py's LESSONS is the
# source of truth for this pairing, but a literal dict here avoids a
# content.py <-> challenges.py import cycle for just 2 entries). Used by
# guided/routes.py to resolve a data_context for a challenge attempt the
# same way it resolves one for the lesson's own step content.
CHALLENGE_TO_LESSON = {
    "01-fundamentos:reto-1": "01-fundamentos",
    "03-agrupar:reto-1": "03-agrupar",
}


def get_challenge_meta(challenge_id):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return None
    return {"prompt": entry["prompt"], "starter_code": entry["starter_code"]}


def run_checker(challenge_id, namespace, context=None):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return _fail("Este reto no existe.")
    try:
        return entry["check"](namespace, context)
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return _fail(f"No se pudo verificar automáticamente ({type(exc).__name__}). Revisa que tu código no tenga errores.")
