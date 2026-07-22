"""Builds a short, plain-language explanation of what a generated chart
shows (Story 7.3).

Server-side, template-based - no LLM call, no cost (NFR11 doesn't apply
here), and it can't hallucinate: the text is derived directly from the same
closed-set inputs {chart_type, columns, valueColumn} that
chart_builder.build_chart_code() already turns into code, so it describes
exactly what the generated code does - nothing it doesn't know.
"""
from app.notebook.chart_builder import TOP_N_SLICES_FOR_TORTA

# Epic 7 code review: chart_builder.py's torta code (Story 7.4) always folds
# everything past the top TOP_N_SLICES_FOR_TORTA categories into a single
# "Otros" slice - this module has no access to real data (same constraint
# chart_builder.py itself documents), so it can't say whether that actually
# happened for a given chart, but it CAN state the static, always-true fact
# about how torta behaves - better than silently describing a chart that
# doesn't match what got drawn.
_TORTA_OTROS_CAVEAT = (
    f" Si hay más de {TOP_N_SLICES_FOR_TORTA} valores distintos, los más "
    'pequeños se agrupan en una porción "Otros".'
)


def build_chart_explanation(chart_type, columns, value_column):
    label = " y ".join(columns) if columns else None

    if chart_type in ("torta", "barras"):
        kind = "de torta" if chart_type == "torta" else "de barras"
        if value_column:
            text = f"Esta gráfica {kind} compara el total de {value_column} para cada valor de {label}."
        else:
            text = f"Esta gráfica {kind} muestra cuántas filas hay para cada valor de {label}."
        if chart_type == "torta":
            text += _TORTA_OTROS_CAVEAT
        return text

    if chart_type == "linea":
        column = columns[0] if columns else None
        if value_column:
            return (
                f"Esta gráfica de línea muestra cómo cambia el total de {value_column} "
                f"a lo largo del tiempo, usando {column} como fecha."
            )
        return f"Esta gráfica de línea muestra cuántas filas hay por fecha, usando {column}."

    if chart_type == "histograma":
        return (
            f"Este histograma muestra cómo se distribuyen los valores de {value_column} "
            "— en qué rangos hay más o menos datos."
        )

    return None
