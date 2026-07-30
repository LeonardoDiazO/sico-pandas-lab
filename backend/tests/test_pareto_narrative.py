import pytest
from google.genai import errors, types

from app.notebook.nl_chart_interpreter import InterpreterUnavailableError
from app.notebook.pareto_narrative import build_stats_payload, generate_pareto_narrative

ROW_STATS = {"total": 171, "cruce_80": 42, "pct_base": 24.6}
GROUP_STATS = {"total": 88, "cruce_80": 28, "pct_base": 31.8}
ROW_RECORDS = [
    {"Legal": "LATIN LOGISTICS COLOMBIA S.A.S.", "N E T O": "$ 12.864.579", "% del total": 6.2, "80/20": "✓"},
    {"Legal": "CONSUMIDOR FINAL", "N E T O": "$ 9.500.000", "% del total": 4.6, "80/20": "✓"},
]
GROUP_RECORDS = [
    {"Legal": "LATIN LOGISTICS COLOMBIA S.A.S.", "N E T O": "$ 37.345.229", "% del total": 17.9, "80/20": "✓"},
    {"Legal": "CONSUMIDOR FINAL", "N E T O": "$ 20.000.000", "% del total": 9.6, "80/20": "✓"},
]


class _FakeCandidate:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason


class _FakeResponse:
    def __init__(self, text, finish_reason=types.FinishReason.STOP):
        self.text = text
        self.candidates = [_FakeCandidate(finish_reason)]


class _FakeModels:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.last_call_kwargs = None

    def generate_content(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeClient:
    def __init__(self, response=None, exc=None):
        self.models = _FakeModels(response=response, exc=exc)


def _build_stats(row_stats=ROW_STATS, group_stats=GROUP_STATS, value_row="neto", value_group="neto", label="cliente"):
    return build_stats_payload(row_stats, ROW_RECORDS, group_stats, GROUP_RECORDS, value_row, value_group, label)


# --- build_stats_payload ---------------------------------------------------


def test_build_stats_payload_shape():
    payload = build_stats_payload(ROW_STATS, ROW_RECORDS, GROUP_STATS, GROUP_RECORDS, "N E T O", "N E T O", "Legal")
    assert payload == {
        "columna_valor_fila": "N E T O",
        "filas_resumen": ROW_STATS,
        "filas": ROW_RECORDS,
        "columna_agrupacion": "Legal",
        "columna_valor_grupo": "N E T O",
        "grupos_resumen": GROUP_STATS,
        "grupos": GROUP_RECORDS,
    }


# --- generate_pareto_narrative: happy path ----------------------------------


def test_returns_stripped_narrative_text():
    client = _FakeClient(response=_FakeResponse("  Un análisis breve.  "))
    stats = _build_stats()
    result = generate_pareto_narrative(stats, client=client)
    assert result == "Un análisis breve."


def test_full_row_and_group_records_are_sent_not_just_a_top_entity():
    """User feedback: replaces the earlier top-1-only NFR11 test - the user
    explicitly chose to send the complete row/group lists ("Todo (los 88
    grupos y las 171 filas completos)"), so both entries of each fixture
    list (not only the first) must reach the model, including the second
    group ("CONSUMIDOR FINAL") that a top-1-only payload would have hidden."""
    client = _FakeClient(response=_FakeResponse("texto"))
    stats = _build_stats()
    generate_pareto_narrative(stats, client=client)
    sent = client.models.last_call_kwargs["contents"]
    assert "LATIN LOGISTICS COLOMBIA S.A.S." in sent
    assert "12.864.579" in sent
    assert "37.345.229" in sent
    assert "CONSUMIDOR FINAL" in sent
    assert "9.500.000" in sent
    assert "20.000.000" in sent


# --- generate_pareto_narrative: unavailable / error handling ----------------


def test_empty_response_text_raises_interpreter_unavailable():
    client = _FakeClient(response=_FakeResponse(""))
    stats = _build_stats()
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_whitespace_only_response_text_raises_interpreter_unavailable():
    client = _FakeClient(response=_FakeResponse("   "))
    stats = _build_stats()
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_safety_blocked_finish_reason_raises_interpreter_unavailable():
    """Unlike nl_chart_interpreter.py's "not resolved" outcome (a normal,
    expected shape for that module), this module has no such closed-set
    fallback shape to degrade to - a blocked narrative has nothing useful to
    show, so it's treated as unavailable."""
    response = _FakeResponse("texto", finish_reason=types.FinishReason.SAFETY)
    client = _FakeClient(response=response)
    stats = _build_stats()
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_provider_error_raises_interpreter_unavailable():
    client = _FakeClient(exc=errors.ServerError(503, {"error": {"message": "unavailable"}}))
    stats = _build_stats()
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_missing_api_key_raises_interpreter_unavailable_without_hitting_the_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    stats = _build_stats()
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats)
