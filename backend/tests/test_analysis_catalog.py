"""build_catalog() unit tests - a fake WorkerManager stands in for the real
one so these never spin up a real worker subprocess (same reasoning as
test_worker_manager.py's own docstring), just record what code strings it
was asked to execute and hand back canned CellResult-shaped dicts."""
from app.notebook.analysis_catalog import MAX_AUTO_BLOCKS, build_catalog


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
    only_metrics = [c for c in CLASSIFICATIONS if c["role"] != "dimension"]
    assert build_catalog("s1", manager, "df", only_metrics) == []

    only_dimensions = [c for c in CLASSIFICATIONS if c["role"] == "dimension"]
    assert build_catalog("s1", manager, "df", only_dimensions) == []


def test_generates_one_block_per_usable_dimension_and_metric():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 3})
    blocks = build_catalog("s1", manager, "df", CLASSIFICATIONS)
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


def test_excludes_high_cardinality_dimensions():
    manager = _FakeManager(unique_counts={"Vendedor": 5, "Ciudad": 500})
    blocks = build_catalog("s1", manager, "df", CLASSIFICATIONS)
    assert len(blocks) == 1
    assert blocks[0]["dimension"] == "Vendedor"


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
