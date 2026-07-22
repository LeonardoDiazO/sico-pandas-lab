"""Builds a short, plain-language explanation of what a generated chart
shows (Story 7.3).

Server-side, template-based - no LLM call, no cost (NFR11 doesn't apply
here), and it can't hallucinate: the text is derived directly from the same
closed-set inputs {chart_type, columns, valueColumn} that
chart_builder.build_chart_code() already turns into code, so it describes
exactly what the generated code does - nothing it doesn't know.
"""
from app.notebook.chart_builder import TOP_N_CATEGORIES_BEFORE_OTROS

# chart_builder.py's torta AND barras code always fold everything past the
# top TOP_N_CATEGORIES_BEFORE_OTROS categories into a single "Otros" slice/bar
# (Story 7.4, extended to barras once multi-column combinations - Story 7.2 -
# made 80+ unique combinations common) - this module has no access to real
# data (same constraint chart_builder.py itself documents), so it can't say
# whether that actually happened for a given chart, but it CAN state the
# static, always-true fact about how these two chart types behave - better
# than silently describing a chart that doesn't match what got drawn.
def _otros_caveat(chart_type):
    noun = "porción" if chart_type == "torta" else "barra"
    return (
        f" Si hay más de {TOP_N_CATEGORIES_BEFORE_OTROS} valores distintos, los más "
        f'pequeños se agrupan en una {noun} "Otros".'
    )


def build_chart_explanation(chart_type, columns, value_column):
    label = " y ".join(columns) if columns else None

    if chart_type in ("torta", "barras"):
        kind = "de torta" if chart_type == "torta" else "de barras"
        if value_column:
            text = f"Esta gráfica {kind} compara el total de {value_column} para cada valor de {label}."
        else:
            text = f"Esta gráfica {kind} muestra cuántas filas hay para cada valor de {label}."
        text += _otros_caveat(chart_type)
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
