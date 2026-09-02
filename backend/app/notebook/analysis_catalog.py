"""Runs a fixed, deterministic catalog of Pareto analyses across every
dimension x metrica combination a confirmed column classification enables -
pure pandas, zero AI. Reuses table_builder.py's build_summary_code() (the
same generator the manual "Resumen y porcentaje por columna" panel already
calls) rather than building a second analysis engine: this module only
decides WHICH combinations to run, never how to compute one.

One execute() call per block, not two: build_summary_code() already returns,
in a single cell, (1) the grouped/summed table with %/cumulative-%/80-20
marker columns, (2) a full Pareto chart (bars + cumulative-% line + the 80%
reference line - not a plain bar chart), and (3) a printed business-language
sentence ("3 de 5 vendedores concentran el 82% del total.") via stdout. This
module's only job on top of that is lifting that sentence into its own
`insight` field so the frontend can headline it, and attaching the same
plain-language `explanation` the manual flow already gets (table_explanation.
py) - nothing here recomputes anything build_summary_code doesn't already
compute.
"""
from app.notebook.chart_builder import HIGH_CARDINALITY_THRESHOLD, _looks_like_money, build_cardinality_check_code
from app.notebook.semantic_classifier import ROLE_DIMENSION, ROLE_METRICA
from app.notebook.table_builder import build_summary_code
from app.notebook.table_explanation import build_summary_explanation

# Each block costs 2 sequential execute() calls (one shared cardinality
# probe per dimension + one build_summary_code call) inside the same
# worker.lock-serialized session - capped so confirming a classification on
# a wide file can't queue minutes of sequential execution before the user
# sees anything.
MAX_AUTO_BLOCKS = 8


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


def _usable_dimensions(session_id, manager, variable, dimensions):
    """A dimension only earns a spot in the catalog if grouping by it stays
    legible - same HIGH_CARDINALITY_THRESHOLD the manual torta/barras
    cardinality-warning flow already enforces (chart_builder.py), checked
    here via the same build_cardinality_check_code() rather than a second
    threshold or a stale ratio from the upload-time profile."""
    usable = []
    for dim in dimensions:
        check = manager.execute(session_id, build_cardinality_check_code(variable, [dim]))
        try:
            unique_count = int(check.get("result_text"))
        except (TypeError, ValueError):
            continue
        if unique_count <= HIGH_CARDINALITY_THRESHOLD:
            usable.append(dim)
    return usable


def build_catalog(session_id, manager, variable, classifications):
    """Returns a list of blocks:
    {"titulo", "dimension", "metrica", "insight", "resultado"}.

    `insight` is the business-language headline ("3 de 5 vendedores
    concentran el 82% del total.") or None if the group had no clear 80%
    crossing (e.g. a single group). `resultado` is a CellResult-shaped dict
    (result_html/chart_svg/error/...) plus `explanation` - the exact same
    shape /summary-table already returns, so it renders through the same
    frontend component. Its own `stdout` is cleared once `insight` has
    lifted that sentence out, so the UI never shows the same sentence twice.
    """
    dimensions = _names_with_role(classifications, ROLE_DIMENSION)
    metrics = _prioritized_metrics(_names_with_role(classifications, ROLE_METRICA))
    if not dimensions or not metrics:
        return []

    usable_dimensions = _usable_dimensions(session_id, manager, variable, dimensions)

    blocks = []
    for metric in metrics:
        for dim in usable_dimensions:
            if len(blocks) >= MAX_AUTO_BLOCKS:
                return blocks
            resultado = manager.execute(session_id, build_summary_code(variable, [dim], metric))
            insight = None
            if not resultado.get("error"):
                insight = (resultado.get("stdout") or "").strip() or None
                resultado = {
                    **resultado,
                    "stdout": None,
                    "explanation": build_summary_explanation([dim], metric),
                }
            blocks.append(
                {
                    "titulo": f"{metric} por {dim}",
                    "dimension": dim,
                    "metrica": metric,
                    "insight": insight,
                    "resultado": resultado,
                }
            )
    return blocks
