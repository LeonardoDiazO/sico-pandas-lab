import json

import pytest
from google.genai import errors, types

from app.notebook.nl_chart_interpreter import (
    InterpreterUnavailableError,
    build_interpretation_schema,
    interpret_chart_request,
)

COLUMNS = [
    {"name": "Vendedor", "type": "categorica"},
    {"name": "Fecha", "type": "fecha"},
    {"name": "Neto", "type": "numerica"},
    {"name": "Cliente", "type": "categorica"},
    {"name": "NIT", "type": "descartable"},
]


class _FakeCandidate:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason


class _FakeResponse:
    def __init__(self, payload, finish_reason=types.FinishReason.STOP):
        self.text = json.dumps(payload)
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


# --- build_interpretation_schema -------------------------------------------------


def test_schema_column_enum_only_includes_categorica_and_fecha():
    schema = build_interpretation_schema(COLUMNS)
    column_enum = schema["properties"]["column"]["anyOf"][0]["enum"]
    assert set(column_enum) == {"Vendedor", "Fecha", "Cliente"}


def test_schema_value_column_enum_only_includes_numerica():
    schema = build_interpretation_schema(COLUMNS)
    value_enum = schema["properties"]["valueColumn"]["anyOf"][0]["enum"]
    assert value_enum == ["Neto"]


def test_schema_chart_type_enum_matches_chart_builder_closed_set():
    from app.notebook.chart_builder import CHART_TYPES

    schema = build_interpretation_schema(COLUMNS)
    chart_type_enum = schema["properties"]["chartType"]["anyOf"][0]["enum"]
    assert set(chart_type_enum) == CHART_TYPES


def test_schema_every_object_forbids_additional_properties():
    schema = build_interpretation_schema(COLUMNS)
    assert schema["additionalProperties"] is False


def test_schema_with_no_numeric_columns_forbids_any_value_column():
    schema = build_interpretation_schema(
        [{"name": "Vendedor", "type": "categorica"}]
    )
    value_column_schema = schema["properties"]["valueColumn"]
    assert value_column_schema == {"type": "null"}


# --- interpret_chart_request: happy paths -----------------------------------------


def test_valid_torta_selection_is_returned_as_is():
    payload = {
        "resolved": True,
        "column": "Vendedor",
        "valueColumn": None,
        "chartType": "torta",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)
    assert result == {
        "resolved": True,
        "column": "Vendedor",
        "valueColumn": None,
        "chartType": "torta",
        "reason": None,
    }


def test_valid_histograma_selection_needs_only_value_column():
    payload = {
        "resolved": True,
        "column": None,
        "valueColumn": "Neto",
        "chartType": "histograma",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("distribución del neto", COLUMNS, client=client)
    assert result["resolved"] is True
    assert result["chartType"] == "histograma"
    assert result["valueColumn"] == "Neto"


def test_model_not_resolved_is_returned_as_is():
    payload = {
        "resolved": False,
        "column": None,
        "valueColumn": None,
        "chartType": None,
        "reason": "No puedo comparar dos periodos con una sola gráfica.",
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("compárame julio contra junio", COLUMNS, client=client)
    assert result["resolved"] is False
    assert result["column"] is None
    assert "comparar" in result["reason"]


# --- interpret_chart_request: application-level re-validation (defense in depth) --


def test_torta_with_numeric_column_is_normalized_to_not_resolved():
    # Should not be constructible under the schema's enum, but re-validate anyway.
    payload = {
        "resolved": True,
        "column": "Neto",
        "valueColumn": None,
        "chartType": "torta",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("torta rara", COLUMNS, client=client)
    assert result["resolved"] is False
    assert result["column"] is None
    assert result["chartType"] is None


def test_column_not_in_supplied_list_is_normalized_to_not_resolved():
    payload = {
        "resolved": True,
        "column": "ColumnaInventada",
        "valueColumn": None,
        "chartType": "barras",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("barras por algo raro", COLUMNS, client=client)
    assert result["resolved"] is False


def test_unrecognized_chart_type_is_normalized_to_not_resolved():
    payload = {
        "resolved": True,
        "column": "Vendedor",
        "valueColumn": None,
        "chartType": "dispersión",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("dispersión por vendedor", COLUMNS, client=client)
    assert result["resolved"] is False


def test_histograma_without_value_column_is_normalized_to_not_resolved():
    payload = {
        "resolved": True,
        "column": None,
        "valueColumn": None,
        "chartType": "histograma",
        "reason": None,
    }
    client = _FakeClient(response=_FakeResponse(payload))
    result = interpret_chart_request("histograma sin nada", COLUMNS, client=client)
    assert result["resolved"] is False


# --- interpret_chart_request: NFR11 — only metadata travels, never data -----------


def test_only_column_metadata_and_question_are_sent_no_dataframe_content():
    payload = {"resolved": False, "column": None, "valueColumn": None, "chartType": None, "reason": "x"}
    client = _FakeClient(response=_FakeResponse(payload))
    interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)
    sent = client.models.last_call_kwargs
    serialized = json.dumps(sent, default=str)
    assert "hazme una torta por vendedor" in serialized
    for column in COLUMNS:
        assert column["name"] in serialized


def test_schema_is_sent_as_response_json_schema_not_response_schema():
    """The schema this module builds is a raw JSON Schema dict (enum/anyOf/
    additionalProperties), not a Pydantic model - must go through
    response_json_schema, not response_schema (which expects a different
    shape and would silently misbehave or reject this dict)."""
    payload = {"resolved": False, "column": None, "valueColumn": None, "chartType": None, "reason": "x"}
    client = _FakeClient(response=_FakeResponse(payload))
    interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)
    config = client.models.last_call_kwargs["config"]
    assert config.response_json_schema is not None
    assert config.response_mime_type == "application/json"


# --- interpret_chart_request: unavailable / error handling ------------------------


def test_rate_limit_error_raises_interpreter_unavailable():
    client = _FakeClient(exc=errors.ClientError(429, {"error": {"message": "rate limited"}}))
    with pytest.raises(InterpreterUnavailableError):
        interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)


def test_authentication_error_from_provider_raises_interpreter_unavailable():
    """The provider rejected a *configured* key (e.g. revoked) - distinct
    from the "no key at all" case below, which the SDK signals differently."""
    client = _FakeClient(exc=errors.ClientError(401, {"error": {"message": "invalid api key"}}))
    with pytest.raises(InterpreterUnavailableError):
        interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)


def test_missing_api_key_raises_interpreter_unavailable_without_hitting_the_network(monkeypatch):
    """Regression test (Epic 6 code review, still enforced after the Gemini
    swap): when GEMINI_API_KEY is unset and no `client` is injected,
    interpret_chart_request() must degrade to InterpreterUnavailableError -
    not let a raw exception escape. genai.Client() itself DOES raise for a
    missing key (a plain ValueError, stricter than the old Anthropic SDK),
    but the explicit env-var check here means this never depends on that
    SDK-specific behavior - exercises the real construction path (no fake
    client passed) to prove it never reaches genai.Client() at all."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(InterpreterUnavailableError):
        interpret_chart_request("hazme una torta por vendedor", COLUMNS)


def test_connection_error_raises_interpreter_unavailable():
    client = _FakeClient(exc=errors.ServerError(503, {"error": {"message": "unavailable"}}))
    with pytest.raises(InterpreterUnavailableError):
        interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)


def test_safety_blocked_finish_reason_is_treated_as_not_resolved():
    """Gemini's equivalent of Anthropic's stop_reason == 'refusal' - the
    model declined rather than erroring. Must be a normal "not resolved"
    outcome (AC2), not raise InterpreterUnavailableError (which would
    incorrectly read as a service outage and refund the usage slot the
    route already spent for this request)."""
    response = _FakeResponse(
        {"resolved": False, "column": None, "valueColumn": None, "chartType": None, "reason": None},
        finish_reason=types.FinishReason.SAFETY,
    )
    client = _FakeClient(response=response)
    result = interpret_chart_request("hazme una torta por vendedor", COLUMNS, client=client)
    assert result["resolved"] is False


def test_blank_question_raises_value_error():
    client = _FakeClient(response=_FakeResponse({}))
    with pytest.raises(ValueError):
        interpret_chart_request("   ", COLUMNS, client=client)
