"""Server-side challenge checkers for the guided-learning module.

Each checker runs INSIDE the sandboxed execution worker, straight against the
learner's own namespace, right after their code executes -- the checker
function itself is never sent to the browser, so the answer can't be read
from the network tab.

Checks compare against a value recomputed from the learner's OWN loaded
DataFrame (real sico data or the lesson's synthetic fallback, whichever is in
the namespace) rather than a hardcoded expected number. That is what lets the
same check pass whether the learner practiced on the real table or the
try/except synthetic example -- there is no fixed "golden answer".
"""


def _fail(message):
    return {"passed": False, "message": message}


def _ok(message):
    return {"passed": True, "message": message}


def _check_fundamentos_total(ns):
    if "df_02_movimiento" not in ns:
        return _fail(
            "Necesitas `df_02_movimiento` en esta sesión antes del reto -- "
            "carga la tabla desde el panel de arriba, o corre primero el "
            "paso 1.2 de esta lección (crea el ejemplo de práctica)."
        )
    if "total_cantidad" not in ns:
        return _fail("Aún no existe una variable llamada `total_cantidad`. Guarda tu respuesta con ese nombre exacto.")

    esperado = ns["df_02_movimiento"]["mov_cantidad"].sum()
    try:
        coincide = abs(float(ns["total_cantidad"]) - float(esperado)) < 1e-6
    except (TypeError, ValueError):
        return _fail("`total_cantidad` debe ser un número (el resultado de sumar una columna).")

    if not coincide:
        return _fail(
            "`total_cantidad` no coincide con la suma real de la columna `mov_cantidad`. "
            "Pista: `df_02_movimiento['mov_cantidad'].sum()`."
        )
    return _ok("¡Correcto! Esa es la suma total de mov_cantidad.")


def _check_agrupar_total_por_item(ns):
    import pandas as pd

    if "df_02_movimiento" not in ns:
        return _fail(
            "Necesitas `df_02_movimiento` en esta sesión antes del reto -- "
            "carga la tabla desde el panel de arriba, o corre primero el paso 3.1 de esta lección."
        )
    if "resultado" not in ns:
        return _fail("Aún no existe una variable llamada `resultado`. Guarda tu respuesta con ese nombre exacto.")

    resultado = ns["resultado"]
    if not isinstance(resultado, pd.Series):
        return _fail(
            "`resultado` debe ser una Series -- el resultado de agrupar por una columna y "
            "resumir una sola métrica (por ejemplo `.groupby('mov_item')['mov_neto'].sum()`)."
        )

    esperado = ns["df_02_movimiento"].groupby("mov_item")["mov_neto"].sum().sort_values(ascending=False)
    try:
        coincide_valores = resultado.sort_index().equals(esperado.sort_index())
    except Exception:
        return _fail("No se pudo comparar tu resultado -- revisa que agrupaste por 'mov_item' y sumaste 'mov_neto'.")

    if not coincide_valores:
        return _fail(
            "Los valores no coinciden con agrupar `df_02_movimiento` por 'mov_item' y sumar "
            "'mov_neto'. Revisa la columna y la operación que usaste."
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


def get_challenge_meta(challenge_id):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return None
    return {"prompt": entry["prompt"], "starter_code": entry["starter_code"]}


def run_checker(challenge_id, namespace):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return _fail("Este reto no existe.")
    try:
        return entry["check"](namespace)
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return _fail(f"No se pudo verificar automáticamente ({type(exc).__name__}). Revisa que tu código no tenga errores.")
