import io

import pandas as pd
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    return app.test_client()


def _sales_xlsx_bytes():
    rows = [
        {"Vendedor": v, "Ciudad": c, "Factura": f"F{i:04d}", "Neto": 1000.0 + i}
        for i, (v, c) in enumerate(
            [("Ana", "Bogota"), ("Luis", "Medellin"), ("Ana", "Cali"), ("Marta", "Bogota")] * 5
        )
        for f in [f"F{i:04d}"]
    ]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_classify_columns_without_upload_is_rejected(client):
    response = client.post("/api/notebook/classify-columns")
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_classify_columns_uses_fallback_without_api_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_sales_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.post("/api/notebook/classify-columns")
    body = response.get_json()
    assert response.status_code == 200
    assert body["data"]["usedAssistant"] is False
    roles = {c["name"]: c["role"] for c in body["data"]["classifications"]}
    assert roles["Vendedor"] == "dimension"
    assert roles["Ciudad"] == "dimension"
    assert roles["Neto"] == "metrica"
    assert roles["Factura"] == "identificador"


def test_auto_analysis_without_classifications_is_rejected(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_sales_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )
    response = client.post("/api/notebook/auto-analysis", json={})
    assert response.status_code == 400


def test_auto_analysis_end_to_end_generates_blocks_with_charts_and_tables(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_sales_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )
    classify_response = client.post("/api/notebook/classify-columns")
    classifications = classify_response.get_json()["data"]["classifications"]

    response = client.post("/api/notebook/auto-analysis", json={"classifications": classifications})
    body = response.get_json()
    assert response.status_code == 200
    bloques = body["data"]["bloques"]
    assert len(bloques) > 0
    for bloque in bloques:
        assert bloque["resultado"]["error"] is None
        assert bloque["resultado"]["result_html"] is not None
        assert bloque["resultado"]["chart_svg"] is not None
        assert bloque["resultado"]["explanation"]
        assert bloque["resultado"]["stdout"] is None  # lifted into `insight`, not shown twice

    resumen = body["data"]["resumen"]
    assert resumen["filas"] == 20  # 4 unique rows * 5 repeats, see _sales_xlsx_bytes()
    assert resumen["bloques"] == len(bloques)
    assert resumen["dimensiones"] >= 1
    assert resumen["metricas"] >= 1
