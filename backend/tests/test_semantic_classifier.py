import json

from app.notebook.semantic_classifier import (
    ROLE_DESCARTAR,
    ROLE_DIMENSION,
    ROLE_FECHA,
    ROLE_IDENTIFICADOR,
    ROLE_METRICA,
    classify_columns,
)

COLUMNS = [
    {"name": "Vendedor", "type": "categorica", "uniqueRatio": 0.05, "sampleValues": ["Ana", "Luis"]},
    {"name": "Fecha", "type": "fecha", "uniqueRatio": 0.9, "sampleValues": ["2026-01-01"]},
    {"name": "Neto", "type": "numerica", "uniqueRatio": 0.95, "sampleValues": ["30000", "12000"]},
    {"name": "Factura", "type": "categorica", "uniqueRatio": 0.99, "sampleValues": ["F001", "F002"]},
    {"name": "Columna vacía", "type": "descartable", "uniqueRatio": 0.0, "sampleValues": []},
]


class _FakeModels:
    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc

    def generate_content(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return type("Resp", (), {"text": self._text})()


class _FakeClient:
    def __init__(self, text=None, exc=None):
        self.models = _FakeModels(text=text, exc=exc)


# --- fallback (no client / no API key) --------------------------------------


def test_fallback_classifies_by_type_and_cardinality(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = classify_columns(COLUMNS)
    assert result["usedAssistant"] is False
    roles = {c["name"]: c["role"] for c in result["classifications"]}
    assert roles["Vendedor"] == ROLE_DIMENSION
    assert roles["Fecha"] == ROLE_FECHA
    assert roles["Neto"] == ROLE_METRICA
    assert roles["Factura"] == ROLE_IDENTIFICADOR  # uniqueRatio 0.99, categorica
    assert roles["Columna vacía"] == ROLE_DESCARTAR


def test_empty_columns_list_returns_empty_classification_without_calling_client():
    result = classify_columns([], client=_FakeClient(text="should never be read"))
    assert result == {"classifications": [], "usedAssistant": False}


# --- LLM path -----------------------------------------------------------------


def test_llm_classification_overlays_fallback_for_resolved_columns():
    payload = {
        "classifications": [
            {"name": "Vendedor", "role": "dimension"},
            {"name": "Fecha", "role": "fecha"},
            {"name": "Neto", "role": "metrica"},
            {"name": "Factura", "role": "identificador"},
            {"name": "Columna vacía", "role": "descartar"},
        ]
    }
    client = _FakeClient(text=json.dumps(payload))
    result = classify_columns(COLUMNS, client=client)
    assert result["usedAssistant"] is True
    roles = {c["name"]: c["role"] for c in result["classifications"]}
    assert roles["Vendedor"] == "dimension"


def test_llm_response_with_unknown_column_name_is_ignored():
    payload = {"classifications": [{"name": "NoExiste", "role": "metrica"}]}
    client = _FakeClient(text=json.dumps(payload))
    result = classify_columns(COLUMNS, client=client)
    # No valid entries survived -> falls back entirely, usedAssistant False.
    assert result["usedAssistant"] is False


def test_llm_response_with_invalid_role_falls_back_for_that_column():
    payload = {
        "classifications": [
            {"name": "Vendedor", "role": "no-es-un-rol-valido"},
            {"name": "Neto", "role": "metrica"},
        ]
    }
    client = _FakeClient(text=json.dumps(payload))
    result = classify_columns(COLUMNS, client=client)
    assert result["usedAssistant"] is True
    roles = {c["name"]: c["role"] for c in result["classifications"]}
    assert roles["Vendedor"] == ROLE_DIMENSION  # fell back for this one column
    assert roles["Neto"] == "metrica"  # LLM's valid answer kept


def test_empty_response_text_falls_back():
    client = _FakeClient(text=None)
    result = classify_columns(COLUMNS, client=client)
    assert result["usedAssistant"] is False


def test_malformed_json_falls_back():
    client = _FakeClient(text="not json")
    result = classify_columns(COLUMNS, client=client)
    assert result["usedAssistant"] is False


def test_api_error_falls_back():
    from google.genai import errors

    client = _FakeClient(exc=errors.APIError(500, {"message": "boom"}, response=None))
    result = classify_columns(COLUMNS, client=client)
    assert result["usedAssistant"] is False
