import pytest
from google.genai import errors, types

from app.notebook.nl_chart_interpreter import InterpreterUnavailableError
from app.notebook.pareto_narrative import build_stats_payload, generate_pareto_narrative

ROW_STATS = {"total": 171, "cruce_80": 42, "pct_base": 24.6, "top_valor": "$ 12.864.579", "top_pct": 6.2}
GROUP_STATS = {
    "total": 88,
    "cruce_80": 28,
    "pct_base": 31.8,
    "top_valor": "$ 37.345.229",
    "top_pct": 17.9,
    "top_grupo_nombre": "LATIN LOGISTICS COLOMBIA S.A.S.",
}


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


# --- build_stats_payload ---------------------------------------------------


def test_build_stats_payload_shape():
    payload = build_stats_payload(ROW_STATS, GROUP_STATS, "N E T O", "N E T O", "Cliente_2")
    assert payload == {
        "columna_valor_fila": "N E T O",
        "filas": ROW_STATS,
        "columna_agrupacion": "Cliente_2",
        "columna_valor_grupo": "N E T O",
        "grupos": GROUP_STATS,
    }


# --- generate_pareto_narrative: happy path ----------------------------------


def test_returns_stripped_narrative_text():
    client = _FakeClient(response=_FakeResponse("  Un análisis breve.  "))
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    result = generate_pareto_narrative(stats, client=client)
    assert result == "Un análisis breve."


def test_only_the_precomputed_stats_are_sent_no_raw_data():
    """NFR11 equivalent for this module (see its own docstring): only
    aggregate numbers travel to the LLM - nothing that isn't already one of
    the fields build_stats_payload() assembles."""
    client = _FakeClient(response=_FakeResponse("texto"))
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    generate_pareto_narrative(stats, client=client)
    sent = client.models.last_call_kwargs["contents"]
    assert "LATIN LOGISTICS COLOMBIA S.A.S." in sent
    assert "12.864.579" in sent
    assert "37.345.229" in sent


# --- generate_pareto_narrative: unavailable / error handling ----------------


def test_empty_response_text_raises_interpreter_unavailable():
    client = _FakeClient(response=_FakeResponse(""))
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_whitespace_only_response_text_raises_interpreter_unavailable():
    client = _FakeClient(response=_FakeResponse("   "))
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_safety_blocked_finish_reason_raises_interpreter_unavailable():
    """Unlike nl_chart_interpreter.py's "not resolved" outcome (a normal,
    expected shape for that module), this module has no such closed-set
    fallback shape to degrade to - a blocked narrative has nothing useful to
    show, so it's treated as unavailable."""
    response = _FakeResponse("texto", finish_reason=types.FinishReason.SAFETY)
    client = _FakeClient(response=response)
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_provider_error_raises_interpreter_unavailable():
    client = _FakeClient(exc=errors.ServerError(503, {"error": {"message": "unavailable"}}))
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats, client=client)


def test_missing_api_key_raises_interpreter_unavailable_without_hitting_the_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    stats = build_stats_payload(ROW_STATS, GROUP_STATS, "neto", "neto", "cliente")
    with pytest.raises(InterpreterUnavailableError):
        generate_pareto_narrative(stats)
