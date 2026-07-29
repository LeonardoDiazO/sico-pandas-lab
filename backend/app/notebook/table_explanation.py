"""Builds a short, plain-language explanation of what the no-code table
flow shows (Story 8.1/8.2 follow-up - user feedback: "% del total y %
acumulado, explicación de qué hace referencia esto").

Server-side, template-based - no LLM call, no cost, and it can't
hallucinate: the text is derived directly from the same closed-set inputs
{value_column, columns} that table_builder.py's build_sort_code()/
build_summary_code() already turn into code, so it describes exactly what
the generated code computes - nothing it doesn't know. Same principle
chart_explanation.py already established for charts.
"""


def build_sort_explanation(value_column):
    return (
        f"Cada fila es un registro individual, ordenado por {value_column}. "
        f'"% del total" es qué parte de la suma de todo el {value_column} representa esa fila sola. '
        '"% acumulado" va sumando esos porcentajes en el orden mostrado, para ver rápido cuánto llevas '
        "acumulado hasta llegar a esa fila."
    )


def build_summary_explanation(columns, value_column):
    label = " y ".join(columns)
    return (
        f"Cada fila es un valor distinto de {label}, con la suma de {value_column} para ese grupo. "
        f'"% del total" es qué parte de la suma de TODO el {value_column} representa ese grupo. '
        '"% acumulado" va sumando esos porcentajes de mayor a menor, para ver rápido cuántos grupos '
        "concentran la mayoría del total."
    )
