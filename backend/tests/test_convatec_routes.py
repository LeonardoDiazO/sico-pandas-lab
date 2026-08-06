import io

import openpyxl
import pandas as pd
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    return app.test_client()


def _maestros_xlsx_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tables"
    ws["B2"] = "PRODUCTO"
    ws["K2"] = "REPRESENTANTES"
    ws["O2"] = "CONVENIOS"

    # Joined by ICC (HyperSoft's own code), not SAP Code -- see
    # pipeline.homologar_productos docstring for why.
    for i, h in enumerate(["ICC", "Franquicia", "Familia", "Clase", "Grupo", "Clasificación Cuota Producto"]):
        ws.cell(row=4, column=2 + i, value=h)
    ws.cell(row=5, column=2, value="1004113")
    ws.cell(row=5, column=3, value="CONTINENCE")
    ws.cell(row=5, column=4, value="Flexiseal")
    ws.cell(row=5, column=5, value="0")
    ws.cell(row=5, column=6, value="Continence Care")
    ws.cell(row=5, column=7, value="1. CCC")

    for i, h in enumerate(["Convenio", "Grupo de vendedores", "Representante"]):
        ws.cell(row=4, column=11 + i, value=h)
    ws.cell(row=5, column=11, value="SALUD TOTAL")
    ws.cell(row=5, column=12, value=45)
    ws.cell(row=5, column=13, value="Katerine Bonilla")

    for i, h in enumerate(["CONVENIO", "CIUDAD", "CLIENTE", "CODIGO SAP"]):
        ws.cell(row=4, column=15 + i, value=h)
    ws.cell(row=5, column=15, value="SALUD TOTAL")
    ws.cell(row=5, column=16, value="BOGOTA")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _productos_xlsx_bytes():
    buf = io.BytesIO()
    rows = [
        {
            "Codigo": "1004113",
            "Convenio": "X",
            "Departamento": "META",
            "Valor Total": 100.0,
            "Paciente": "Jose Perez",
            "Identificación": "123",
        },
        {
            "Codigo": "1004113",
            "Convenio": "X",
            "Departamento": "ANTIOQUIA",
            "Valor Total": 200.0,
            "Paciente": "Ana Ruiz",
            "Identificación": "456",
        },
    ]
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


def _envios_nacionales_xlsx_bytes():
    buf = io.BytesIO()
    rows = [{"Departamento": "META", "Valor Total": 30.0, "Paciente": "Filtro Inesperado"}]
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


HEADERS = {"X-Session-Id": "test-session"}


def test_full_cycle_upload_maestros_ventas_procesar_and_descargar(client):
    maestros_resp = client.post(
        "/api/convatec/tablas-maestras",
        data={"file": (_maestros_xlsx_bytes(), "maestros.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert maestros_resp.status_code == 200
    assert maestros_resp.get_json()["success"] is True

    ventas_resp = client.post(
        "/api/convatec/ventas/productos",
        data={"file": (_productos_xlsx_bytes(), "productos.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert ventas_resp.status_code == 200
    ventas_body = ventas_resp.get_json()["data"]
    # PHI columns never make it past ingestion, even for a session-scoped upload.
    assert "Paciente" not in ventas_body["columns"]
    assert "Identificación" not in ventas_body["columns"]

    procesar_resp = client.post(
        "/api/convatec/procesar", json={"mes": 3}, headers=HEADERS
    )
    assert procesar_resp.status_code == 200
    procesar_body = procesar_resp.get_json()["data"]
    assert procesar_body["totalLineas"] == 2

    comision_resp = client.post(
        "/api/convatec/comision-ilustrativa",
        json={"valorReferencia": 100},
        headers=HEADERS,
    )
    assert comision_resp.status_code == 200
    assert comision_resp.get_json()["data"]["esOficial"] is False

    descargar_resp = client.get("/api/convatec/descargar", headers=HEADERS)
    assert descargar_resp.status_code == 200
    assert descargar_resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_envios_nacionales_upload_also_drops_phi_columns_defensively(client):
    """NFR-2 must not rely on the assumption that envios-nacionales never
    carries patient data -- drop_patient_columns runs for every tipo."""
    resp = client.post(
        "/api/convatec/ventas/envios-nacionales",
        data={"file": (_envios_nacionales_xlsx_bytes(), "envios.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "Paciente" not in resp.get_json()["data"]["columns"]


def test_procesar_without_master_tables_fails_clearly(client):
    resp = client.post("/api/convatec/procesar", json={}, headers={"X-Session-Id": "sin-maestros"})
    assert resp.status_code == 400
    assert "tablas maestras" in resp.get_json()["message"]


def test_procesar_rejects_bool_as_mes(client):
    client.post(
        "/api/convatec/tablas-maestras",
        data={"file": (_maestros_xlsx_bytes(), "maestros.xlsx")},
        content_type="multipart/form-data",
        headers={"X-Session-Id": "bool-mes"},
    )
    resp = client.post(
        "/api/convatec/procesar", json={"mes": True}, headers={"X-Session-Id": "bool-mes"}
    )
    assert resp.status_code == 400


def test_comision_ilustrativa_rejects_bool_and_non_finite_valor(client):
    session = {"X-Session-Id": "comision-validacion"}
    client.post(
        "/api/convatec/tablas-maestras",
        data={"file": (_maestros_xlsx_bytes(), "maestros.xlsx")},
        content_type="multipart/form-data",
        headers=session,
    )
    client.post(
        "/api/convatec/ventas/productos",
        data={"file": (_productos_xlsx_bytes(), "productos.xlsx")},
        content_type="multipart/form-data",
        headers=session,
    )
    client.post("/api/convatec/procesar", json={"mes": 3}, headers=session)

    bool_resp = client.post("/api/convatec/comision-ilustrativa", json={"valorReferencia": True}, headers=session)
    assert bool_resp.status_code == 400

    inf_resp = client.post("/api/convatec/comision-ilustrativa", json={"valorReferencia": float("inf")}, headers=session)
    assert inf_resp.status_code == 400


def test_descargar_without_ciclo_procesado_fails_clearly(client):
    resp = client.get("/api/convatec/descargar", headers={"X-Session-Id": "sin-ciclo"})
    assert resp.status_code == 400


def test_upload_ventas_rejects_unknown_tipo(client):
    resp = client.post(
        "/api/convatec/ventas/algo-invalido",
        data={"file": (_productos_xlsx_bytes(), "x.xlsx")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_reiniciar_clears_session_state(client):
    session = {"X-Session-Id": "para-reiniciar"}
    client.post(
        "/api/convatec/tablas-maestras",
        data={"file": (_maestros_xlsx_bytes(), "maestros.xlsx")},
        content_type="multipart/form-data",
        headers=session,
    )
    reset_resp = client.post("/api/convatec/reiniciar", headers=session)
    assert reset_resp.status_code == 200

    procesar_resp = client.post("/api/convatec/procesar", json={}, headers=session)
    assert procesar_resp.status_code == 400  # maestros were cleared by reiniciar


def test_two_sessions_do_not_share_state(client):
    client.post(
        "/api/convatec/tablas-maestras",
        data={"file": (_maestros_xlsx_bytes(), "maestros.xlsx")},
        content_type="multipart/form-data",
        headers={"X-Session-Id": "session-a"},
    )
    resp_b = client.post("/api/convatec/procesar", json={}, headers={"X-Session-Id": "session-b"})
    assert resp_b.status_code == 400  # session-b never uploaded maestros itself
