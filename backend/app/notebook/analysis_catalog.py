"""Runs a fixed, deterministic catalog of analyses across every dimension x
metrica combination a confirmed column classification enables - pure pandas,
zero AI. Reuses table_builder.py's build_summary_code() (the same generator
the manual "Resumen y porcentaje por columna" panel already calls) rather
than building a second analysis engine: this module only decides WHICH
combinations to run, never how to compute one.

One execute() call per block: build_summary_code() returns, in a single
cell, (1) the grouped table with %/cumulative-%/80-20 marker columns, (2) a
Pareto chart and (3) a printed business-language sentence ("3 de 5
vendedores concentran el 82% del total.") plus, when some groups leave the
ranking (net <= 0 or "(vacío)"), "Fuera del ranking: ..." lines. This module
lifts those lines into `insight` / `fueraDelRanking` so the frontend can
show them, attaches the plain-language `explanation`, and returns the exact
`codigo` it ran so the learner can open it in the Notebook ("Ver el código")
and get the same table.

Auditoría 2026-11-18 additions:
- per-metric aggregation (`agg`: sum/mean/count) instead of always summing;
- a dimension with more than HIGH_CARDINALITY_THRESHOLD values is no longer
  dropped: it gets a "Top 15 + Otros (k)" card;
- a monthly trend block per `fecha` column x main metric (max 2, not counted
  against MAX_AUTO_BLOCKS);
- `filters` (dashboard cross-filter): every card - and the cardinality used
  to pick dimensions - is computed over the filtered rows.
"""
import re

from app.notebook.chart_builder import HIGH_CARDINALITY_THRESHOLD, _looks_like_money
from app.notebook.semantic_classifier import ROLE_DIMENSION, ROLE_FECHA, ROLE_METRICA
from app.notebook.table_builder import (
    AGG_LABELS,
    AGGREGATIONS,
    OUT_OF_RANKING_PREFIX,
    _filter_lines,
    _money_format_expr,
    agg_title,
    build_summary_code,
)
from app.notebook.table_explanation import build_summary_explanation

# Each block costs one execute() call (plus one shared cardinality probe per
# dimension) inside the same worker.lock-serialized session - capped so
# confirming a classification on a wide file can't queue minutes of
# sequential execution before the user sees anything.
MAX_AUTO_BLOCKS = 8
# Trend blocks are extra and do not consume MAX_AUTO_BLOCKS.
MAX_TREND_BLOCKS = 2
# Cards of high-cardinality dimensions show this many groups + "Otros (k)".
TOP_N = HIGH_CARDINALITY_THRESHOLD

_OUT_OF_RANKING_LINE = re.compile(rf"^{re.escape(OUT_OF_RANKING_PREFIX)} (.*) = (.*) \((.*)\)$")


def _names_with_role(classifications, role):
    return [c["name"] for c in classifications if c["role"] == role]


def _prioritized_metrics(metric_names):
    """Money-looking metrics first (chart_builder.py's own _looks_like_money
    heuristic, e.g. "neto"/"ventas") - they tend to be the headline KPI a
    business user cares about most, so when MAX_AUTO_BLOCKS caps the
    catalog, those survive first rather than whatever column happened to
    come first in the file."""
    money = [m for m in metric_names if _looks_like_money(m)]
    other = [m for m in metric_names if m not in money]
    return money + other


def _metric_aggregations(classifications, aggregations):
    """metric name -> 'sum' | 'mean' | 'count'. Taken from the explicit
    `aggregations` map, else from an `agg` key on the classification entry,
    else 'sum'."""
    result = {}
    for c in classifications:
        if c["role"] != ROLE_METRICA:
            continue
        agg = (aggregations or {}).get(c["name"]) or c.get("agg") or "sum"
        result[c["name"]] = agg if agg in AGGREGATIONS else "sum"
    return result


def _flatten(text):
    """Column names can contain line breaks (multi-row Excel headers); a
    header comment must stay on one line or the rest becomes code."""
    return " ".join(str(text).split())


def _with_header(title, code, filters):
    header = [f"# Análisis automático: {_flatten(title)}"]
    if filters:
        detail = "; ".join(f"{_flatten(f['column'])} = {', '.join(_flatten(v) for v in f['values'])}" for f in filters)
        header.append(f"# Filtrado por: {detail}")
    header.append("# Generado por el tablero sin código. Ejecútalo para ver la misma tabla.")
    return "\n".join(header) + "\n" + code


def _cardinality_code(variable, column, filters):
    filter_lines, source = _filter_lines(variable, filters or [])
    return "\n".join(filter_lines + [f"{source}[{column!r}].nunique()"])


def _dimension_cardinalities(session_id, manager, variable, dimensions, filters, skipped=None):
    """Distinct values of each dimension, over the FILTERED rows. Dimensions
    with fewer than 2 values carry no comparison and are reported in
    `skipped`; every other one is kept (high-cardinality ones get Top N)."""
    usable = []
    for dim in dimensions:
        check = manager.execute(session_id, _cardinality_code(variable, dim, filters))
        try:
            unique_count = int(check.get("result_text"))
        except (TypeError, ValueError):
            continue
        if unique_count < 2:
            # A single value (e.g. a "Bodega" column that is always "3")
            # yields a one-bar "1 de 1 concentra el 100%" card - no
            # information, and it spends a slot of MAX_AUTO_BLOCKS.
            if skipped is not None:
                skipped.append({"dimension": dim, "valores": unique_count})
            continue
        usable.append((dim, unique_count))
    return usable


def _split_stdout(stdout):
    """(insight, fuera_del_ranking, other_lines) from a summary cell's stdout."""
    insight = None
    fuera = []
    other = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _OUT_OF_RANKING_LINE.match(line)
        if match:
            fuera.append({"grupo": match.group(1), "valor": match.group(2), "motivo": match.group(3)})
        elif insight is None and ("concentra" in line):
            insight = line
        else:
            other.append(line)
    return insight, fuera, other


def build_trend_code(variable, date_column, metric, agg="sum", filters=None):
    """Monthly series of `metric` by `date_column`, with empty months filled
    with 0 and a note when the last month is incomplete. Handles real dates,
    text dates, YYYYMMDD numbers and Excel serial numbers (origin 1899-12-30,
    fractional values allowed) without raising."""
    filter_lines, source = _filter_lines(variable, filters or [])
    agg_expr = "count()" if agg == "count" else ("mean()" if agg == "mean" else "sum()")
    is_money = _looks_like_money(metric) and agg != "count"
    value_display = _money_format_expr("_serie") if is_money else "_serie.round(2)"
    lines = filter_lines + [
        f"_crudo = {source}[{date_column!r}]",
        "if pd.api.types.is_datetime64_any_dtype(_crudo):",
        "    _fechas = _crudo",
        "else:",
        "    _num = pd.to_numeric(_crudo, errors='coerce')",
        "    if _num.notna().sum() > 0 and _num.notna().mean() >= 0.9:",
        "        _validos = _num.dropna()",
        "        if ((_validos >= 19000101) & (_validos <= 21001231)).mean() >= 0.9:",
        "            _fechas = pd.to_datetime(_num.round().astype('Int64').astype(str), format='%Y%m%d', errors='coerce')",
        "        elif ((_validos >= 190001) & (_validos <= 210012) & (_validos % 100 >= 1) & (_validos % 100 <= 12)).mean() >= 0.9:",
        "            _fechas = pd.to_datetime(_num.round().astype('Int64').astype(str), format='%Y%m', errors='coerce')",
        "        elif ((_validos >= 1900) & (_validos <= 2100)).mean() >= 0.9:",
        "            _fechas = pd.to_datetime(_num.round().astype('Int64').astype(str), format='%Y', errors='coerce')",
        "        else:",
        "            _fechas = pd.to_datetime(_num.where((_num > 0) & (_num < 2958466)), unit='D', origin='1899-12-30', errors='coerce')",
        "    else:",
        # ISO text (2026-01-05) is year-month-day; anything else from a
        # Colombian Excel (05/01/2026) is day-first.
        "        _iso = _crudo.astype(str).str.strip().str.match(r'^\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}').mean() >= 0.5",
        "        _fechas = pd.to_datetime(_crudo, errors='coerce', dayfirst=not _iso)",
        f"_base = {source}.assign(_mes=_fechas.dt.to_period('M')).dropna(subset=['_mes'])",
        "if len(_base) == 0:",
        "    print('No hay fechas válidas para calcular la tendencia.')",
        "    _serie = pd.Series(dtype=float)",
        "else:",
        f"    _serie = _base.groupby('_mes')[{metric!r}].{agg_expr}",
        "    _serie = _serie.reindex(pd.period_range(_serie.index.min(), _serie.index.max(), freq='M'), fill_value=0)",
        "    _ultima = _fechas.max()",
        # Period reports dated on the 1st of every month are complete months.
        "    _parcial = bool(_ultima.day < _ultima.days_in_month and _fechas.dt.day.nunique() > 1)",
        "    if len(_serie) >= 2:",
        "        _comparable = _serie.iloc[:-1] if _parcial and len(_serie) >= 3 else _serie",
        "        _act, _ant = _comparable.iloc[-1], _comparable.iloc[-2]",
        "        _var = ((_act - _ant) / abs(_ant) * 100) if _ant else float('nan')",
        "        _txt_var = 'sin base de comparación' if pd.isna(_var) else f'{_var:+.0f}% frente a {_comparable.index[-2]}'",
        f"        print(f'{{_comparable.index[-1]}}: {{_txt_var}} ({_flatten(metric)}).')",
        "    if _parcial:",
        "        print(f'El último mes ({_serie.index[-1]}) está incompleto: hay datos hasta el {_ultima:%d/%m/%Y}.')",
        "    _serie.plot(kind='line', marker='o', figsize=(10, 4))",
        f"    plt.title({('Tendencia mensual de ' + _flatten(metric))!r})",
        "    plt.tight_layout()",
        "_serie.index = _serie.index.astype(str)",
        "_serie.index.name = 'Mes'",
        f"_tabla = pd.DataFrame({{{metric!r}: _serie}})",
        "_tabla['Variación %'] = (_serie.pct_change() * 100).round(1).replace([float('inf'), float('-inf')], float('nan'))",
        f"_tabla.assign(**{{{metric!r}: {value_display}}})",
    ]
    return "\n".join(lines)


def _run_block(session_id, manager, title, code, filters):
    codigo = _with_header(title, code, filters)
    resultado = manager.execute(session_id, codigo)
    return codigo, resultado


def build_catalog(session_id, manager, variable, classifications, report=None, filters=None, aggregations=None):
    """Returns a list of blocks:
    {"tipo": "pareto" | "tendencia", "titulo", "dimension", "metrica", "agg",
     "insight", "fueraDelRanking", "topN", "valoresDistintos", "codigo",
     "resultado"}.

    `insight` is the business-language headline or None. `resultado` is a
    CellResult-shaped dict plus `explanation` - the same shape /summary-table
    returns. Its `stdout` is cleared once its sentences were lifted out.
    For a trend block `dimension` is the date column.

    `report` (optional dict) is filled with what the catalog left out:
    `omitidas` (dimensions with fewer than 2 distinct values) and
    `limite_alcanzado` (True when MAX_AUTO_BLOCKS cut the catalog short).
    """
    if report is not None:
        report.setdefault("omitidas", [])
        report.setdefault("limite_alcanzado", False)
    filters = filters or []
    dimensions = _names_with_role(classifications, ROLE_DIMENSION)
    metrics = _prioritized_metrics(_names_with_role(classifications, ROLE_METRICA))
    date_columns = _names_with_role(classifications, ROLE_FECHA)
    aggs = _metric_aggregations(classifications, aggregations)
    if not metrics or (not dimensions and not date_columns):
        return []

    usable = _dimension_cardinalities(
        session_id, manager, variable, dimensions, filters, report["omitidas"] if report is not None else None
    )

    blocks = []
    limit_hit = False
    for metric in metrics:
        agg = aggs.get(metric, "sum")
        for dim, unique_count in usable:
            if len(blocks) >= MAX_AUTO_BLOCKS:
                limit_hit = True
                break
            top_n = TOP_N if unique_count > HIGH_CARDINALITY_THRESHOLD else None
            title = agg_title(metric, dim, agg)
            code = build_summary_code(variable, [dim], metric, filters=filters, agg=agg, top_n=top_n)
            codigo, resultado = _run_block(session_id, manager, title, code, filters)
            insight, fuera = None, []
            if not resultado.get("error"):
                insight, fuera, _rest = _split_stdout(resultado.get("stdout"))
                resultado = {
                    **resultado,
                    "stdout": None,
                    "explanation": build_summary_explanation([dim], metric),
                }
            blocks.append(
                {
                    "tipo": "pareto",
                    "titulo": title,
                    "dimension": dim,
                    "metrica": metric,
                    "agg": agg,
                    "insight": insight,
                    "fueraDelRanking": fuera,
                    "topN": top_n,
                    "valoresDistintos": unique_count,
                    "codigo": codigo,
                    "resultado": resultado,
                }
            )
        if limit_hit:
            break
    if report is not None and limit_hit:
        report["limite_alcanzado"] = True

    main_metric = metrics[0]
    main_agg = aggs.get(main_metric, "sum")
    for date_column in date_columns[:MAX_TREND_BLOCKS]:
        title = f"Tendencia mensual de {main_metric} por {date_column}"
        code = build_trend_code(variable, date_column, main_metric, main_agg, filters)
        codigo, resultado = _run_block(session_id, manager, title, code, filters)
        insight = None
        if not resultado.get("error"):
            lines = [line.strip() for line in (resultado.get("stdout") or "").splitlines() if line.strip()]
            insight = " ".join(lines) or None
            resultado = {
                **resultado,
                "stdout": None,
                "explanation": (
                    f"Cada fila es un mes, con {AGG_LABELS[main_agg].lower()} de {main_metric} en ese mes. "
                    "Los meses sin datos aparecen en 0 para no saltarse ninguno, y "
                    '"Variación %" compara cada mes con el anterior.'
                ),
            }
        blocks.append(
            {
                "tipo": "tendencia",
                "titulo": title,
                "dimension": date_column,
                "metrica": main_metric,
                "agg": main_agg,
                "insight": insight,
                "fueraDelRanking": [],
                "topN": None,
                "valoresDistintos": None,
                "codigo": codigo,
                "resultado": resultado,
            }
        )
    return blocks
