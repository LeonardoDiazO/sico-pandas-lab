"""Server-side challenge checkers for the guided-learning module.

Each checker runs INSIDE the sandboxed execution worker, straight against the
learner's own namespace, right after their code executes -- the checker
function itself is never sent to the browser, so the answer can't be read
from the network tab.

Anti-cheat (2026-11): the expected answer is NEVER recomputed from the
learner's namespace. A learner could otherwise replace or mutate `df` and
then assign an answer computed from their own version. The reference data
comes from one of two server-owned places:

- `pristine`: an untouched copy the worker keeps of every DataFrame the
  backend injected with `bind` (an uploaded Excel, a sico table);
- the lesson's own synthetic table, rebuilt from its canonical constructor
  (the `except NameError:` branch of the lesson step, in content.py) in a
  separate namespace - see `canonical_tables()`. A table the learner typed
  themselves before running the lesson step is never used as reference.

Each checker takes an optional ``context`` (see app.guided.data_context):
{"table_var": str, "roles": {role: column_name}}. It tells the checker which
DataFrame/columns are "in play" for THIS attempt -- resolved once, server
side, from the learner's excel_profiler profile if they uploaded their own
data, or left as None to fall back to each checker's own default context
(the lesson's historic synthetic names).
"""
from app.guided import content

# Lesson synthetic tables that have a canonical server-side constructor.
SNAPSHOT_TABLE_VARS = ("df_02_movimiento", "df_02_item", "df_clientes", "df_ventas")

_DEFAULT_CONTEXT_FUNDAMENTOS = {"table_var": "df_02_movimiento", "roles": {"num1": "mov_cantidad"}}
_DEFAULT_CONTEXT_AGRUPAR = {"table_var": "df_02_movimiento", "roles": {"cat": "mov_item", "num2": "mov_neto"}}
_DEFAULT_CONTEXT_GRAFICAS = {"table_var": "df_02_movimiento", "roles": {"cat": "mov_item", "num1": "mov_cantidad"}}

ORIGINAL_DATA_HINT = (
    "Recuerda que el reto se compara contra los datos originales: si modificaste o reemplazaste "
    "`{table}`, vuelve a cargarla (o corre otra vez el paso de la lección) antes de responder."
)

# Per worker process (= per session): table_var -> [DataFrame, ...]
_canonical_cache = {}


def _fail(message):
    return {"passed": False, "message": message}


def _ok(message):
    return {"passed": True, "message": message}


def canonical_tables(table_var):
    """Every server-built version of a lesson synthetic table, executed from
    the canonical constructors in content.py in a namespace of its own and
    cached for the life of this worker. Several lessons define the same
    variable with slightly different example rows, and a learner may have
    run any of them first, so all of them are valid references."""
    if table_var not in _canonical_cache:
        import numpy as np
        import pandas as pd

        tables = []
        for source in content.canonical_table_sources(table_var):
            scratch = {"pd": pd, "np": np}
            exec(compile(source, "<referencia>", "exec"), scratch)  # noqa: S102 - server-owned code
            if table_var in scratch:
                tables.append(scratch[table_var])
        _canonical_cache[table_var] = tables
    return [t.copy() for t in _canonical_cache[table_var]]


def _safe(compute, *args):
    """Runs compute(*args), or returns None when a reference version lacks a
    column the computation needs (lessons define slightly different example
    tables under the same name)."""
    try:
        return compute(*args)
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def reference_tables(table_var, pristine):
    """Reference versions of `table_var` for a check: the pristine copy of a
    bound table if there is one, else the canonical synthetic versions."""
    if pristine and table_var in pristine:
        original = pristine[table_var]
        return [original.copy() if hasattr(original, "copy") else original]
    if table_var in SNAPSHOT_TABLE_VARS:
        return canonical_tables(table_var)
    return []


def _missing_table(table_var, step_hint):
    return _fail(
        f"Necesitas `{table_var}` en esta sesión antes del reto -- carga la tabla desde el panel de "
        f"arriba, o corre primero {step_hint} de esta lección (crea el ejemplo de práctica)."
    )


def _same_rows(a, b):
    """Same columns (any order) and the same rows (any order)."""
    import pandas as pd

    if not isinstance(a, pd.DataFrame) or not isinstance(b, pd.DataFrame):
        return False
    if set(map(str, a.columns)) != set(map(str, b.columns)) or len(a) != len(b):
        return False
    cols = sorted(b.columns, key=str)
    left = sorted(map(tuple, a[cols].astype(str).values.tolist()))
    right = sorted(map(tuple, b[cols].astype(str).values.tolist()))
    return left == right


def _same_series_values(result, expected):
    """Same index labels and values, ignoring order and int/float dtype."""
    import pandas as pd

    if not isinstance(result, pd.Series):
        return False
    try:
        left = result.sort_index()
        right = expected.sort_index()
    except TypeError:
        return False
    if len(left) != len(right):
        return False
    if [str(i) for i in left.index] != [str(i) for i in right.index]:
        return False
    try:
        return all(abs(float(x) - float(y)) < 1e-6 for x, y in zip(left.values, right.values))
    except (TypeError, ValueError):
        return False


# --- 00 -----------------------------------------------------------------


def _check_python_total(ns, context=None, pristine=None, had_chart=False):
    for name in ("precio", "cantidad"):
        if name not in ns:
            return _fail(f"Aún no existe la variable `{name}`. Créala con ese nombre exacto.")
    if "total_compra" not in ns:
        return _fail("Aún no existe una variable llamada `total_compra`. Guarda tu respuesta con ese nombre exacto.")
    try:
        precio, cantidad, total = float(ns["precio"]), float(ns["cantidad"]), float(ns["total_compra"])
    except (TypeError, ValueError):
        return _fail("`precio`, `cantidad` y `total_compra` deben ser números.")
    if precio != 25000 or cantidad != 4:
        return _fail("Usa exactamente `precio = 25000` y `cantidad = 4`.")
    if abs(total - precio * cantidad) > 1e-9:
        return _fail("`total_compra` debe ser `precio` multiplicado por `cantidad` (usa el operador `*`).")
    return _ok("¡Correcto! Guardaste valores en variables y operaste con ellas.")


# --- 01 -----------------------------------------------------------------


def _check_fundamentos_total(ns, context=None, pristine=None, had_chart=False):
    context = context or _DEFAULT_CONTEXT_FUNDAMENTOS
    table_var = context["table_var"]
    qty_col = context["roles"]["num1"]

    if table_var not in ns:
        return _missing_table(table_var, "el paso 1.2")
    if "total_cantidad" not in ns:
        return _fail("Aún no existe una variable llamada `total_cantidad`. Guarda tu respuesta con ese nombre exacto.")
    try:
        respuesta = float(ns["total_cantidad"])
    except (TypeError, ValueError):
        return _fail("`total_cantidad` debe ser un número (el resultado de sumar una columna).")

    referencias = reference_tables(table_var, pristine)
    if not referencias:
        return _missing_table(table_var, "el paso 1.2")
    totales = [_safe(lambda r: float(r[qty_col].sum()), ref) for ref in referencias]
    if not any(t is not None and abs(respuesta - t) < 1e-6 for t in totales):
        return _fail(
            f"`total_cantidad` no coincide con la suma real de la columna `{qty_col}`. "
            f"Pista: `{table_var}['{qty_col}'].sum()`. " + ORIGINAL_DATA_HINT.format(table=table_var)
        )
    return _ok(f"¡Correcto! Esa es la suma total de {qty_col}.")


# --- 02 -----------------------------------------------------------------


def _check_filtrar_ordenar(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    table_var = "df_02_movimiento"
    if table_var not in ns:
        return _missing_table(table_var, "el paso 2.1")
    if "top_movimientos" not in ns:
        return _fail("Aún no existe una variable llamada `top_movimientos`. Guarda tu respuesta con ese nombre exacto.")
    resultado = ns["top_movimientos"]
    if not isinstance(resultado, pd.DataFrame):
        return _fail("`top_movimientos` debe ser un DataFrame: el resultado de filtrar filas de la tabla.")

    for ref in reference_tables(table_var, pristine):
        esperado = _safe(lambda r: r[r["mov_cantidad"] > 0].sort_values("mov_neto", ascending=False), ref)
        if esperado is not None and _same_rows(resultado, esperado):
            netos = list(resultado["mov_neto"])
            if netos != sorted(netos, reverse=True):
                return _fail(
                    "Filtraste bien, pero falta ordenar por `mov_neto` de mayor a menor -- usa "
                    "`.sort_values('mov_neto', ascending=False)`."
                )
            return _ok("¡Muy bien! Filtraste las cantidades positivas y ordenaste de mayor a menor.")
    return _fail(
        "Las filas de `top_movimientos` no coinciden con las de cantidad mayor que 0. Pista: "
        "`df_02_movimiento[df_02_movimiento['mov_cantidad'] > 0]`. " + ORIGINAL_DATA_HINT.format(table=table_var)
    )


# --- 03 -----------------------------------------------------------------


def _check_agrupar_total_por_item(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    context = context or _DEFAULT_CONTEXT_AGRUPAR
    table_var = context["table_var"]
    cat_col = context["roles"]["cat"]
    value_col = context["roles"]["num2"]

    if table_var not in ns:
        return _missing_table(table_var, "el paso 3.1")
    if "resultado" not in ns:
        return _fail("Aún no existe una variable llamada `resultado`. Guarda tu respuesta con ese nombre exacto.")

    resultado = ns["resultado"]
    if not isinstance(resultado, pd.Series):
        return _fail(
            "`resultado` debe ser una Series -- el resultado de agrupar por una columna y "
            f"resumir una sola métrica (por ejemplo `.groupby('{cat_col}')['{value_col}'].sum()`)."
        )

    coincide = False
    for ref in reference_tables(table_var, pristine):
        esperado = _safe(lambda r: r.groupby(cat_col)[value_col].sum(), ref)
        if esperado is not None and _same_series_values(resultado, esperado):
            coincide = True
            break
    if not coincide:
        return _fail(
            f"Los valores no coinciden con agrupar `{table_var}` por '{cat_col}' y sumar "
            f"'{value_col}'. Revisa la columna y la operación que usaste. "
            + ORIGINAL_DATA_HINT.format(table=table_var)
        )

    valores = list(resultado.values)
    if valores != sorted(valores, reverse=True):
        return _fail(
            "Los valores agrupados están bien, pero falta ordenar de mayor a menor -- "
            "agrega `.sort_values(ascending=False)`."
        )
    return _ok("¡Perfecto! Agrupaste, sumaste y ordenaste correctamente.")


# --- 04 -----------------------------------------------------------------


def _check_combinar(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    for table_var in ("df_02_movimiento", "df_02_item"):
        if table_var not in ns:
            return _missing_table(table_var, "el paso 4.1")
    if "con_descripcion" not in ns:
        return _fail("Aún no existe una variable llamada `con_descripcion`. Guarda tu respuesta con ese nombre exacto.")
    resultado = ns["con_descripcion"]
    if not isinstance(resultado, pd.DataFrame):
        return _fail("`con_descripcion` debe ser un DataFrame: el resultado de `pd.merge(...)`.")
    for col in ("mov_item", "item_descripcion"):
        if col not in resultado.columns:
            return _fail(f"A `con_descripcion` le falta la columna `{col}` -- revisa las tablas que combinaste.")

    def _pares(df):
        return sorted(map(tuple, df[["mov_item", "item_descripcion"]].astype(str).values.tolist()))

    for movimiento in reference_tables("df_02_movimiento", pristine):
        for item in reference_tables("df_02_item", pristine):
            esperado = _safe(
                lambda m, i: pd.merge(m, i, left_on="mov_item", right_on="item_codigo", how="left"), movimiento, item
            )
            if esperado is not None and len(resultado) == len(esperado) and _pares(resultado) == _pares(esperado):
                return _ok("¡Excelente! Cruzaste las dos tablas sin perder ningún movimiento.")
    return _fail(
        "`con_descripcion` no coincide con un `pd.merge(df_02_movimiento, df_02_item, left_on='mov_item', "
        "right_on='item_codigo', how='left')`. Revisa las columnas del cruce y el `how`. "
        + ORIGINAL_DATA_HINT.format(table="df_02_movimiento")
    )


# --- 05 -----------------------------------------------------------------


def _check_graficas(ns, context=None, pristine=None, had_chart=False):
    context = context or _DEFAULT_CONTEXT_GRAFICAS
    table_var = context["table_var"]
    cat_col = context["roles"]["cat"]
    value_col = context["roles"]["num1"]

    if table_var not in ns:
        return _missing_table(table_var, "el paso 5.1")
    if "serie_grafica" not in ns:
        return _fail("Aún no existe una variable llamada `serie_grafica`. Guarda tu respuesta con ese nombre exacto.")
    esperados = [_safe(lambda r: r.groupby(cat_col)[value_col].sum(), ref) for ref in reference_tables(table_var, pristine)]
    coincide = any(e is not None and _same_series_values(ns["serie_grafica"], e) for e in esperados)
    if not coincide:
        return _fail(
            f"`serie_grafica` no coincide con agrupar `{table_var}` por '{cat_col}' y sumar '{value_col}'. "
            + ORIGINAL_DATA_HINT.format(table=table_var)
        )
    if not had_chart:
        return _fail("Los datos están bien, pero tu código no dibujó ninguna gráfica -- usa `serie_grafica.plot(kind='bar')`.")
    return _ok("¡Genial! Agrupaste y convertiste el resultado en una gráfica.")


# --- 06 -----------------------------------------------------------------


def _check_limpieza(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    table_var = "df_clientes"
    if table_var not in ns:
        return _missing_table(table_var, "el paso 6.1")
    if "clientes_limpios" not in ns:
        return _fail("Aún no existe una variable llamada `clientes_limpios`. Guarda tu respuesta con ese nombre exacto.")
    resultado = ns["clientes_limpios"]
    if not isinstance(resultado, pd.DataFrame):
        return _fail("`clientes_limpios` debe ser un DataFrame.")
    for ref in reference_tables(table_var, pristine):
        esperado = _safe(lambda r: r.drop_duplicates().dropna(subset=["ciudad"]), ref)
        if esperado is not None and _same_rows(resultado, esperado):
            return _ok("¡Bien hecho! Quitaste los duplicados y las filas sin ciudad.")
    return _fail(
        "`clientes_limpios` no coincide con quitar los duplicados (`.drop_duplicates()`) y las filas sin "
        "ciudad (`.dropna(subset=['ciudad'])`). " + ORIGINAL_DATA_HINT.format(table=table_var)
    )


# --- 07 -----------------------------------------------------------------


def _ventas_por_mes(ref):
    import pandas as pd

    fechas = pd.to_datetime(ref["fecha"], errors="coerce")
    return ref.assign(_mes=fechas.dt.to_period("M")).groupby("_mes")["neto"].sum()


def _check_fechas(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    table_var = "df_ventas"
    if table_var not in ns:
        return _missing_table(table_var, "el paso 7.1")
    if "ventas_por_mes" not in ns:
        return _fail("Aún no existe una variable llamada `ventas_por_mes`. Guarda tu respuesta con ese nombre exacto.")
    resultado = ns["ventas_por_mes"]
    if not isinstance(resultado, pd.Series):
        return _fail("`ventas_por_mes` debe ser una Series: un total de `neto` por cada mes.")
    for ref in reference_tables(table_var, pristine):
        esperado = _safe(_ventas_por_mes, ref)
        if esperado is None or len(resultado) != len(esperado):
            continue
        try:
            valores = [float(v) for v in resultado.sort_index().values]
        except (TypeError, ValueError):
            return _fail("`ventas_por_mes` debe contener números (la suma de `neto`).")
        if all(abs(a - float(b)) < 1e-6 for a, b in zip(valores, esperado.sort_index().values)):
            return _ok("¡Correcto! Convertiste las fechas y sumaste las ventas de cada mes.")
    return _fail(
        "`ventas_por_mes` no coincide con la suma de `neto` por mes. Pista: convierte con "
        "`pd.to_datetime(df_ventas['fecha'])` y agrupa por `.dt.to_period('M')`. "
        + ORIGINAL_DATA_HINT.format(table=table_var)
    )


# --- 08 -----------------------------------------------------------------


def _check_razonamiento(ns, context=None, pristine=None, had_chart=False):
    import pandas as pd

    table_var = "df_ventas"
    if table_var not in ns:
        return _missing_table(table_var, "el paso 8.1")
    if "ranking" not in ns:
        return _fail("Aún no existe una variable llamada `ranking`. Guarda tu respuesta con ese nombre exacto.")
    resultado = ns["ranking"]
    if not isinstance(resultado, pd.Series):
        return _fail("`ranking` debe ser una Series: el neto de cada cliente.")
    for ref in reference_tables(table_var, pristine):
        netos = _safe(lambda r: r.groupby("cliente")["neto"].sum(), ref)
        if netos is None:
            continue
        esperado = netos[netos > 0]
        if _same_series_values(resultado, esperado):
            valores = list(resultado.values)
            if valores != sorted(valores, reverse=True):
                return _fail("Los netos están bien, pero falta ordenarlos de mayor a menor.")
            return _ok("¡Exacto! Ese es el ranking por neto, sin los clientes que no suman (neto ≤ 0).")
        if _same_series_values(resultado, netos):
            return _fail(
                "Casi: incluiste clientes con neto ≤ 0. Esos clientes no aportan al total, así que salen "
                "del ranking -- quédate con `netos[netos > 0]`."
            )
    return _fail(
        "`ranking` no coincide con el neto por cliente (`groupby('cliente')['neto'].sum()`) sin los "
        "netos ≤ 0. " + ORIGINAL_DATA_HINT.format(table=table_var)
    )


CHALLENGES = {
    "00-python-desde-cero:reto-1": {
        "prompt": (
            "Reto: crea una variable `precio` con el valor 25000 y otra `cantidad` con el valor 4. "
            "Luego guarda en `total_compra` el resultado de multiplicarlas."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `total_compra`\n",
        "check": _check_python_total,
    },
    "01-fundamentos:reto-1": {
        "prompt": (
            "Reto: usando `df_02_movimiento` (carga la tabla real desde el panel arriba, o "
            "corre el paso 1.2 si aún no lo has hecho), calcula la suma total de la columna "
            "`mov_cantidad` y guárdala en una variable llamada exactamente `total_cantidad`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `total_cantidad`\n",
        "check": _check_fundamentos_total,
    },
    "02-filtrar-ordenar:reto-1": {
        "prompt": (
            "Reto: usando `df_02_movimiento`, quédate solo con las filas cuya `mov_cantidad` sea "
            "mayor que 0, ordénalas por `mov_neto` de mayor a menor y guarda el resultado en "
            "`top_movimientos`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `top_movimientos`\n",
        "check": _check_filtrar_ordenar,
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
    "04-combinar-tablas:reto-1": {
        "prompt": (
            "Reto: combina `df_02_movimiento` con `df_02_item` (cada `mov_item` con su "
            "`item_codigo`, conservando TODOS los movimientos) y guarda el resultado en "
            "`con_descripcion`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `con_descripcion`\n",
        "check": _check_combinar,
    },
    "05-graficas:reto-1": {
        "prompt": (
            "Reto: agrupa `df_02_movimiento` por `mov_item` sumando `mov_cantidad`, guarda el "
            "resultado en `serie_grafica` y dibuja con ella una gráfica de barras."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda la serie en `serie_grafica` y grafícala\n",
        "check": _check_graficas,
    },
    "06-limpieza:reto-1": {
        "prompt": (
            "Reto: a partir de `df_clientes`, quita las filas duplicadas y las filas que no tienen "
            "`ciudad`, y guarda la tabla limpia en `clientes_limpios`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `clientes_limpios`\n",
        "check": _check_limpieza,
    },
    "07-fechas:reto-1": {
        "prompt": (
            "Reto: con `df_ventas`, convierte `fecha` a fecha de verdad y calcula la suma de `neto` "
            "por mes. Guarda esa Series en `ventas_por_mes`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `ventas_por_mes`\n",
        "check": _check_fechas,
    },
    "08-razonamiento:reto-1": {
        "prompt": (
            "Reto: con `df_ventas`, calcula el neto por `cliente`, deja fuera a los clientes con neto "
            "menor o igual a 0, ordena de mayor a menor y guarda el resultado en `ranking`."
        ),
        "starter_code": "# Escribe tu código aquí -- guarda el resultado en `ranking`\n",
        "check": _check_razonamiento,
    },
}


# challenge_id -> the lesson that defines it, derived from content.LESSONS
# (the single source of truth for that pairing). Used by guided/routes.py to
# resolve a data_context for a challenge attempt the same way it resolves one
# for the lesson's own step content.
CHALLENGE_TO_LESSON = {
    lesson["challenge_id"]: lesson["id"] for lesson in content.LESSONS if lesson.get("challenge_id")
}


def get_challenge_meta(challenge_id):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return None
    return {"prompt": entry["prompt"], "starter_code": entry["starter_code"]}


def run_checker(challenge_id, namespace, context=None, pristine=None, had_chart=False):
    entry = CHALLENGES.get(challenge_id)
    if entry is None:
        return _fail("Este reto no existe.")
    try:
        return entry["check"](namespace, context, pristine=pristine or {}, had_chart=had_chart)
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return _fail(f"No se pudo verificar automáticamente ({type(exc).__name__}). Revisa que tu código no tenga errores.")
