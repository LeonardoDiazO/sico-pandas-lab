import io

import pandas as pd
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    return app.test_client()


def _own_xlsx_bytes():
    rows = [
        {"Vendedor": v, "Cantidad": c, "Neto": n}
        for v, c, n in [
            ("Ana", 3, 30000),
            ("Luis", 1, 12000),
            ("Ana", 5, 50000),
            ("Marta", 2, 8000),
            ("Luis", 4, 40000),
        ]
    ]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def test_lesson_without_any_upload_keeps_the_static_synthetic_example(client):
    response = client.get("/api/guided/lessons/01-fundamentos")
    data = response.get_json()["data"]
    step_1_2 = next(s for s in data["steps"] if s["title"].startswith("1.2"))
    assert "df_02_movimiento" in step_1_2["code"]
    assert "mov_cantidad" in step_1_2["code"]


def test_lesson_after_uploading_own_excel_uses_the_real_variable_and_columns(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.get("/api/guided/lessons/01-fundamentos")
    data = response.get_json()["data"]
    step_1_2 = next(s for s in data["steps"] if s["title"].startswith("1.2"))
    assert "df_02_movimiento" not in step_1_2["code"]
    assert "mov_cantidad" not in step_1_2["code"]
    assert "df" in step_1_2["code"]
    assert "Cantidad" in step_1_2["code"]

    # The challenge prompt must stay consistent with the example code above.
    assert "df_02_movimiento" not in data["challenge"]["prompt"]
    assert "Cantidad" in data["challenge"]["prompt"]


def test_lesson_out_of_scope_stays_static_even_after_uploading_own_excel(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )
    response = client.get("/api/guided/lessons/02-filtrar-ordenar")
    data = response.get_json()["data"]
    assert "df_02_movimiento" in data["steps"][0]["code"]


def test_challenge_passes_against_the_learners_own_uploaded_data_end_to_end(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.post(
        "/api/guided/challenge/check",
        json={"code": "total_cantidad = df['Cantidad'].sum()", "challenge_id": "01-fundamentos:reto-1"},
    )
    result = response.get_json()["data"]
    assert result["error"] is None
    assert result["challenge"]["passed"] is True


def test_agrupar_challenge_passes_against_the_learners_own_uploaded_data_end_to_end(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.post(
        "/api/guided/challenge/check",
        json={
            "code": "resultado = df.groupby('Vendedor')['Neto'].sum().sort_values(ascending=False)",
            "challenge_id": "03-agrupar:reto-1",
        },
    )
    result = response.get_json()["data"]
    assert result["error"] is None
    assert result["challenge"]["passed"] is True
