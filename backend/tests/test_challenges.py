import pandas as pd

from app.guided.challenges import run_checker
from app.notebook.execution import build_namespace, execute_code


def _ns_with_movimiento():
    ns = build_namespace()
    execute_code(
        "df_02_movimiento = pd.DataFrame({\n"
        "    'mov_item': ['A100', 'B200', 'A100', 'C300', 'B200'],\n"
        "    'mov_cantidad': [3, 1, 5, 2, 4],\n"
        "    'mov_neto': [30000, 12000, 50000, 8000, 40000],\n"
        "})",
        ns,
    )
    return ns


def test_fundamentos_challenge_passes_on_correct_answer():
    ns = _ns_with_movimiento()
    execute_code("total_cantidad = df_02_movimiento['mov_cantidad'].sum()", ns)
    result = run_checker("01-fundamentos:reto-1", ns)
    assert result["passed"] is True


def test_fundamentos_challenge_fails_on_wrong_value():
    ns = _ns_with_movimiento()
    execute_code("total_cantidad = 0", ns)
    result = run_checker("01-fundamentos:reto-1", ns)
    assert result["passed"] is False


def test_fundamentos_challenge_fails_when_variable_missing():
    ns = _ns_with_movimiento()
    result = run_checker("01-fundamentos:reto-1", ns)
    assert result["passed"] is False
    assert "total_cantidad" in result["message"]


def test_fundamentos_challenge_fails_when_source_table_missing():
    ns = build_namespace()
    result = run_checker("01-fundamentos:reto-1", ns)
    assert result["passed"] is False


def test_agrupar_challenge_passes_on_correct_answer():
    ns = _ns_with_movimiento()
    execute_code(
        "resultado = df_02_movimiento.groupby('mov_item')['mov_neto'].sum().sort_values(ascending=False)",
        ns,
    )
    result = run_checker("03-agrupar:reto-1", ns)
    assert result["passed"] is True


def test_agrupar_challenge_fails_when_not_sorted():
    # Alphabetical groupby order (A100, B200, C300) here is the exact reverse
    # of sum-by-value order, so an unsorted result reliably fails the check.
    ns = build_namespace()
    execute_code(
        "df_02_movimiento = pd.DataFrame({\n"
        "    'mov_item': ['A100', 'B200', 'C300', 'C300'],\n"
        "    'mov_neto': [3000, 16000, 25000, 25000],\n"
        "})",
        ns,
    )
    execute_code("resultado = df_02_movimiento.groupby('mov_item')['mov_neto'].sum()", ns)
    result = run_checker("03-agrupar:reto-1", ns)
    assert result["passed"] is False
    assert "ordenar" in result["message"]


def test_agrupar_challenge_fails_on_wrong_column():
    ns = _ns_with_movimiento()
    execute_code(
        "resultado = df_02_movimiento.groupby('mov_item')['mov_cantidad'].sum().sort_values(ascending=False)",
        ns,
    )
    result = run_checker("03-agrupar:reto-1", ns)
    assert result["passed"] is False


def test_agrupar_challenge_fails_when_not_a_series():
    ns = _ns_with_movimiento()
    execute_code("resultado = df_02_movimiento.groupby('mov_item').sum()", ns)
    result = run_checker("03-agrupar:reto-1", ns)
    assert result["passed"] is False


def test_unknown_challenge_id_fails_gracefully():
    ns = build_namespace()
    result = run_checker("no-existe", ns)
    assert result["passed"] is False


def test_checker_never_raises_on_broken_namespace():
    ns = _ns_with_movimiento()
    execute_code("resultado = 'no soy una serie'", ns)
    result = run_checker("03-agrupar:reto-1", ns)
    assert result["passed"] is False


# --- checks against the learner's own uploaded data (an explicit `context`,
# not the lesson's synthetic df_02_movimiento) -------------------------------


def _ns_with_own_excel():
    ns = build_namespace()
    execute_code(
        "df = pd.DataFrame({\n"
        "    'Vendedor': ['Ana', 'Luis', 'Ana', 'Marta', 'Luis'],\n"
        "    'Cantidad': [3, 1, 5, 2, 4],\n"
        "    'Neto': [30000, 12000, 50000, 8000, 40000],\n"
        "})",
        ns,
    )
    return ns


def test_fundamentos_challenge_passes_against_the_learners_own_columns():
    ns = _ns_with_own_excel()
    execute_code("total_cantidad = df['Cantidad'].sum()", ns)
    context = {"table_var": "df", "roles": {"num1": "Cantidad"}}
    result = run_checker("01-fundamentos:reto-1", ns, context)
    assert result["passed"] is True


def test_fundamentos_challenge_fails_when_the_wrong_own_column_is_summed():
    ns = _ns_with_own_excel()
    execute_code("total_cantidad = df['Neto'].sum()", ns)  # summed the wrong column
    context = {"table_var": "df", "roles": {"num1": "Cantidad"}}
    result = run_checker("01-fundamentos:reto-1", ns, context)
    assert result["passed"] is False


def test_fundamentos_challenge_error_message_names_the_real_column():
    ns = _ns_with_own_excel()
    execute_code("total_cantidad = 0", ns)  # deliberately wrong, to reach the hint message
    context = {"table_var": "df", "roles": {"num1": "Cantidad"}}
    result = run_checker("01-fundamentos:reto-1", ns, context)
    assert result["passed"] is False
    assert "df" in result["message"]
    assert "Cantidad" in result["message"]


def test_agrupar_challenge_passes_against_the_learners_own_columns():
    ns = _ns_with_own_excel()
    execute_code(
        "resultado = df.groupby('Vendedor')['Neto'].sum().sort_values(ascending=False)",
        ns,
    )
    context = {"table_var": "df", "roles": {"cat": "Vendedor", "num2": "Neto"}}
    result = run_checker("03-agrupar:reto-1", ns, context)
    assert result["passed"] is True


def test_agrupar_challenge_fails_on_wrong_column_with_own_data():
    ns = _ns_with_own_excel()
    execute_code(
        "resultado = df.groupby('Vendedor')['Cantidad'].sum().sort_values(ascending=False)",
        ns,
    )
    context = {"table_var": "df", "roles": {"cat": "Vendedor", "num2": "Neto"}}
    result = run_checker("03-agrupar:reto-1", ns, context)
    assert result["passed"] is False
