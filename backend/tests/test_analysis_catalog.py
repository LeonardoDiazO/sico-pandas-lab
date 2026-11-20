"""build_catalog() unit tests - a fake WorkerManager stands in for the real
one so these never spin up a real worker subprocess (same reasoning as
test_worker_manager.py's own docstring), just record what code strings it
was asked to execute and hand back canned CellResult-shaped dicts."""
from app.notebook.analysis_catalog import MAX_AUTO_BLOCKS, TOP_N, build_catalog


def _pareto(blocks):
    return [b for b in blocks if b["tipo"] == "pareto"]


class _FakeManager:
    def __init__(self, unique_counts=None, stdout="3 de 5 categorías concentran el 82% del total."):
        self.unique_counts = unique_counts or {}
        self.stdout = stdout
        self.executed_codes = []

    def execute(self, session_id, code):
        self.executed_codes.append(code)
        # A cardinality-check call looks like `<var>['<col>'].nunique()` -
        # detect it by the code shape (same code chart_builder.py's own
        # build_cardinality_check_code produces) rather than needing a
        # second fake method.
        if ".nunique()" in code:
            for column, count in self.unique_counts.items():
                if repr(column) in code:
                    return {"result_text": str(count), "error": None}
            return {"result_text": "0", "error": None}
        return {
            "result_html": "<table></table>",
            "chart_svg": "<svg></svg>",
            "stdout": self.stdout,
            "error": None,
        }


CLASSIFICATIONS = [
    {"name": "Vendedor", "role": "dimension"},
    {"name": "Ciudad", "role": "dimension"},
    {"name": "Factura", "role": "identificador"},
    {"name": "Neto", "role": "metrica"},
    {"name": "Fecha", "role": "fecha"},
]


def test_no_dimensions_or_no_metrics_returns_no_blocks():
    manager = _FakeManager()
    only_metrics = [c for c in CLASSIFICATIONS if c["role"] not in ("dimension", "fecha")]
    assert build_catalog("s1", manager, "df", only_metrics) == []

    only_dimensions = [c for c in CLASSIFICATIONS if c["role"] == "dimension"]
    assert build_catalog("s1", manager, "df", only_dimensions) == []


def test_generates_one_block_per_usable_dimension_and_metric():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 3})
    blocks = _pareto(build_catalog("s1", manager, "df", CLASSIFICATIONS))
    assert len(blocks) == 2  # 1 metrica (Neto) x 2 usable dimensions
    dims = {b["dimension"] for b in blocks}
    assert dims == {"Vendedor", "Ciudad"}
    assert all(b["metrica"] == "Neto" for b in blocks)
    assert all(b["resultado"]["error"] is None for b in blocks)


def test_block_lifts_stdout_into_insight_and_clears_it_from_resultado():
    manager = _FakeManager(
        unique_counts={"Vendedor": 5}, stdout="3 de 5 vendedores concentran el 82% del total."
    )
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]
    blocks = build_catalog("s1", manager, "df", classifications)
    assert blocks[0]["insight"] == "3 de 5 vendedores concentran el 82% del total."
    assert blocks[0]["resultado"]["stdout"] is None  # lifted out, not shown twice


def test_block_attaches_a_plain_language_explanation():
    manager = _FakeManager(unique_counts={"Vendedor": 5})
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]
    blocks = build_catalog("s1", manager, "df", classifications)
    assert "Vendedor" in blocks[0]["resultado"]["explanation"]
    assert "Neto" in blocks[0]["resultado"]["explanation"]


def test_errored_block_keeps_error_and_has_no_insight():
    class _ErroringManager(_FakeManager):
        def execute(self, session_id, code):
            if ".nunique()" in code:
                return super().execute(session_id, code)
            return {"error": {"type": "TimeoutError", "message": "boom"}, "stdout": None}

    manager = _ErroringManager(unique_counts={"Vendedor": 5})
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]
    blocks = build_catalog("s1", manager, "df", classifications)
    assert blocks[0]["insight"] is None
    assert blocks[0]["resultado"]["error"] is not None


def test_high_cardinality_dimension_gets_a_top_n_card_instead_of_being_dropped():
    """Auditoría 2026-11-18: a dimension with 88 values used to vanish from
    the dashboard. Now it gets a "Top 15 + Otros (k)" card."""
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 88})
    blocks = _pareto(build_catalog("s1", manager, "df", CLASSIFICATIONS))
    by_dim = {b["dimension"]: b for b in blocks}
    assert set(by_dim) == {"Vendedor", "Ciudad"}
    assert by_dim["Ciudad"]["topN"] == TOP_N
    assert by_dim["Ciudad"]["valoresDistintos"] == 88
    assert by_dim["Vendedor"]["topN"] is None
    ciudad_code = by_dim["Ciudad"]["codigo"]
    assert f"if len(_t) > {TOP_N}:" in ciudad_code


def test_respects_max_auto_blocks_cap():
    many_dimensions = [{"name": f"Dim{i}", "role": "dimension"} for i in range(20)]
    many_metrics = [{"name": f"Met{i}", "role": "metrica"} for i in range(3)]
    manager = _FakeManager(unique_counts={f"Dim{i}": 2 for i in range(20)})
    blocks = build_catalog("s1", manager, "df", many_dimensions + many_metrics)
    assert len(blocks) == MAX_AUTO_BLOCKS


def test_prioritizes_money_looking_metrics_first():
    classifications = [
        {"name": "Cantidad", "role": "metrica"},
        {"name": "Neto", "role": "metrica"},  # "neto" is a money keyword
        {"name": "Vendedor", "role": "dimension"},
    ]
    manager = _FakeManager(unique_counts={"Vendedor": 2})
    blocks = build_catalog("s1", manager, "df", classifications)
    assert blocks[0]["metrica"] == "Neto"
    assert blocks[1]["metrica"] == "Cantidad"


def test_non_numeric_cardinality_result_skips_that_dimension():
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]

    class _BrokenManager(_FakeManager):
        def execute(self, session_id, code):
            if ".nunique()" in code:
                return {"result_text": "no-es-un-numero", "error": None}
            return super().execute(session_id, code)

    blocks = build_catalog("s1", _BrokenManager(), "df", classifications)
    assert blocks == []


def test_report_does_not_omit_high_cardinality_dimensions_anymore():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 79})
    report = {}
    blocks = _pareto(build_catalog("s1", manager, "df", CLASSIFICATIONS, report))
    assert [b["dimension"] for b in blocks] == ["Vendedor", "Ciudad"]
    assert report["omitidas"] == []
    assert report["limite_alcanzado"] is False


def test_report_flags_when_max_auto_blocks_cuts_the_catalog():
    many_metrics = [{"name": "Vendedor", "role": "dimension"}] + [
        {"name": f"M{i}", "role": "metrica"} for i in range(MAX_AUTO_BLOCKS + 2)
    ]
    manager = _FakeManager(unique_counts={"Vendedor": 3})
    report = {}
    blocks = build_catalog("s1", manager, "df", many_metrics, report)
    assert len(blocks) == MAX_AUTO_BLOCKS
    assert report["limite_alcanzado"] is True


def test_single_value_dimension_is_omitted_and_reported():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 1})
    report = {}
    blocks = _pareto(build_catalog("s1", manager, "df", CLASSIFICATIONS, report))
    assert [b["dimension"] for b in blocks] == ["Vendedor"]
    assert report["omitidas"] == [{"dimension": "Ciudad", "valores": 1}]


# --- auditoría 2026-11-18 ----------------------------------------------------


def test_block_carries_the_exact_code_it_ran_with_a_one_line_header():
    manager = _FakeManager(unique_counts={"Vendedor": 5})
    classifications = [
        {"name": "Vendedor\nRegión", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
    ]
    manager.unique_counts = {"Vendedor\nRegión": 5}
    blocks = build_catalog("s1", manager, "df", classifications)
    codigo = blocks[0]["codigo"]
    assert codigo in manager.executed_codes
    first_line = codigo.splitlines()[0]
    assert first_line.startswith("# ")
    assert "Vendedor Región" in first_line  # newline flattened, still a comment


def test_mean_aggregation_changes_title_and_generated_code():
    manager = _FakeManager(unique_counts={"Vendedor": 5})
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Precio", "role": "metrica"},
    ]
    blocks = build_catalog("s1", manager, "df", classifications, aggregations={"Precio": "mean"})
    assert blocks[0]["titulo"] == "Promedio de Precio por Vendedor"
    assert blocks[0]["agg"] == "mean"
    assert "['Precio'].mean()" in blocks[0]["codigo"]


def test_out_of_ranking_lines_are_lifted_into_their_own_field():
    stdout = (
        "2 de 3 categorías concentran el 85% del total.\n"
        "Fuera del ranking: (vacío) = $ 1.200 (sin valor en la columna)\n"
        "Fuera del ranking: Luis = $ -300 (neto ≤ 0)\n"
    )
    manager = _FakeManager(unique_counts={"Vendedor": 5}, stdout=stdout)
    classifications = [{"name": "Vendedor", "role": "dimension"}, {"name": "Neto", "role": "metrica"}]
    block = build_catalog("s1", manager, "df", classifications)[0]
    assert block["insight"] == "2 de 3 categorías concentran el 85% del total."
    assert block["fueraDelRanking"] == [
        {"grupo": "(vacío)", "valor": "$ 1.200", "motivo": "sin valor en la columna"},
        {"grupo": "Luis", "valor": "$ -300", "motivo": "neto ≤ 0"},
    ]


def test_trend_blocks_are_extra_and_capped_at_two():
    classifications = [
        {"name": "Vendedor", "role": "dimension"},
        {"name": "Neto", "role": "metrica"},
        {"name": "F1", "role": "fecha"},
        {"name": "F2", "role": "fecha"},
        {"name": "F3", "role": "fecha"},
    ]
    manager = _FakeManager(unique_counts={"Vendedor": 5})
    blocks = build_catalog("s1", manager, "df", classifications)
    trends = [b for b in blocks if b["tipo"] == "tendencia"]
    assert [b["dimension"] for b in trends] == ["F1", "F2"]
    assert all(b["metrica"] == "Neto" for b in trends)


def test_trend_blocks_do_not_consume_max_auto_blocks():
    many = [{"name": f"D{i}", "role": "dimension"} for i in range(MAX_AUTO_BLOCKS)] + [
        {"name": "Neto", "role": "metrica"},
        {"name": "Fecha", "role": "fecha"},
    ]
    manager = _FakeManager(unique_counts={f"D{i}": 3 for i in range(MAX_AUTO_BLOCKS)})
    blocks = build_catalog("s1", manager, "df", many)
    assert len(_pareto(blocks)) == MAX_AUTO_BLOCKS
    assert len([b for b in blocks if b["tipo"] == "tendencia"]) == 1


def test_filters_apply_to_cardinality_probe_and_every_card():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 3})
    filters = [{"column": "Ciudad", "values": ["Cali"]}]
    blocks = build_catalog("s1", manager, "df", CLASSIFICATIONS, filters=filters)
    probes = [c for c in manager.executed_codes if ".nunique()" in c]
    assert probes and all("_filtrado" in c for c in probes)
    assert all("_filtrado" in b["codigo"] for b in blocks)
    assert all("# Filtrado por: Ciudad = Cali" in b["codigo"] for b in blocks)
