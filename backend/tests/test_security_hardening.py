"""Security hardening (auditoría 2026-11-18): sandbox, secrets, capacity,
upload limit, team access key and server-issued sessions. Cases of the spec's
I/O matrix that need a real worker process go through the real app."""
import io
import os

import pandas as pd
import pytest
from flask.testing import FlaskClient

from app import create_app
from app.notebook.execution import build_namespace, execute_code
from app.utils import secrets as app_secrets


def _execute(client, code, session="session-a"):
    response = client.post("/api/notebook/execute", json={"code": code}, headers={"X-Session-Id": session})
    return response


@pytest.fixture
def client():
    return create_app().test_client()


# --- builtins / imports (in-process, no worker needed) ---------------------


@pytest.mark.parametrize(
    "code",
    ["import os", "from os import path", "import subprocess", "import importlib", "__import__('os')", "import builtins"],
)
def test_blocked_imports_raise_a_clear_error(code):
    result = execute_code(code, build_namespace())
    assert result["error"]["type"] == "ImportError"
    assert "no está permitido en este entorno" in result["error"]["message"]


@pytest.mark.parametrize("code", ["open('x.txt')", "eval('1')", "exec('x = 1')", "compile('1', 'a', 'eval')", "input()"])
def test_dangerous_builtins_are_not_available(code):
    result = execute_code(code, build_namespace())
    assert result["error"]["type"] == "NameError"


def test_allowed_imports_still_work_and_library_internals_can_import_freely():
    ns = build_namespace()
    result = execute_code(
        "import math, json, statistics, datetime, re, collections, itertools\n"
        "import numpy as np\n"
        "from scipy import stats\n"
        "f'{pd.Timestamp(\"2026-01-05\"):%d/%m/%Y}'",  # strftime lazily imports `time` in C
        ns,
    )
    assert result["error"] is None
    assert "05/01/2026" in result["result_text"]


def test_urllib_parse_only_exposes_parse_not_request():
    ns = build_namespace()
    ok = execute_code("import urllib.parse as up\nup.quote('a b')", ns)
    assert ok["error"] is None and "a%20b" in ok["result_text"]
    leak = execute_code("import urllib.parse\nurllib.request", ns)
    assert leak["error"] is not None and leak["error"]["type"] == "AttributeError"
    blocked = execute_code("from urllib import request", ns)
    assert blocked["error"]["type"] == "ImportError"


def test_real_builtins_module_is_not_mutated():
    import builtins

    build_namespace()
    assert callable(builtins.open) and callable(builtins.exec)


# --- secrets ---------------------------------------------------------------


def test_create_app_moves_secrets_out_of_the_process_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-gemini-de-prueba")
    monkeypatch.setenv("SICO_DB_PASSWORD", "clave-bd-de-prueba")
    monkeypatch.setenv("SECRET_KEY", "firma-de-prueba")
    app = create_app()
    assert "GEMINI_API_KEY" not in os.environ
    assert "SICO_DB_PASSWORD" not in os.environ
    assert app.config["GEMINI_API_KEY"] == "clave-gemini-de-prueba"
    assert app.config["SECRET_KEY"] == "firma-de-prueba"
    # A second app in the same process still gets them.
    assert create_app().config["GEMINI_API_KEY"] == "clave-gemini-de-prueba"


def test_worker_cannot_read_secrets_through_pandas_os(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-gemini-de-prueba")
    monkeypatch.setenv("SICO_DB_PASSWORD", "clave-bd-de-prueba")
    client = create_app().test_client()
    body = _execute(client, "sorted(pd.io.common.os.environ)").get_json()
    assert body["data"]["error"] is None
    assert "GEMINI_API_KEY" not in body["data"]["result_text"]
    assert "SICO_DB_" not in body["data"]["result_text"]


def test_import_os_is_blocked_inside_the_real_worker(client):
    body = _execute(client, "import os\nos.environ").get_json()
    assert "no está permitido en este entorno" in body["data"]["error"]["message"]


@pytest.mark.parametrize(
    "code",
    [
        "pd.read_csv('/proc/self/environ')",
        "pd.read_pickle('datos.pkl')",
        "pd.DataFrame({'a': [1]}).to_csv('fuga.csv')",
        "np.save('fuga.npy', np.array([1]))",
        "plt.plot([1, 2]); plt.savefig('fuga.png')",
    ],
)
def test_file_io_through_libraries_is_blocked_in_the_worker(client, code):
    body = _execute(client, code).get_json()
    error = body["data"]["error"]
    assert error is not None and error["type"] == "PermissionError"
    assert "no está permitido" in error["message"]


def test_in_memory_io_and_charts_still_work_in_the_worker(client):
    body = _execute(
        client,
        "csv = pd.DataFrame({'a': [1, 2]}).to_csv(index=False)\n"
        "plt.plot([1, 2])\n"
        "csv",
    ).get_json()
    assert body["data"]["error"] is None
    assert body["data"]["chart_svg"]


# --- capacity / upload limit ----------------------------------------------


def test_new_session_beyond_max_sessions_gets_503(monkeypatch):
    monkeypatch.setenv("MAX_SESSIONS", "1")
    client = create_app().test_client()
    assert _execute(client, "1 + 1", session="session-a").status_code == 200
    response = _execute(client, "1 + 1", session="session-b")
    body = response.get_json()
    assert response.status_code == 503
    assert body["success"] is False and body["status"] == 503
    assert "servidor está lleno" in body["message"]
    # The existing session keeps working.
    assert _execute(client, "2 + 2", session="session-a").status_code == 200


def test_upload_over_the_limit_is_rejected_with_413_before_parsing(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    client = create_app().test_client()
    big = io.BytesIO(b"0" * (2 * 1024 * 1024))
    response = client.post(
        "/api/notebook/upload-excel",
        data={"file": (big, "grande.xlsx")},
        content_type="multipart/form-data",
    )
    body = response.get_json()
    assert response.status_code == 413
    assert body["success"] is False and body["status"] == 413
    assert "1 MB" in body["message"]


# --- access key / sessions -------------------------------------------------


def test_access_key_required_when_configured(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_KEY", "clave-del-equipo")
    client = create_app().test_client()

    health = client.get("/api/health").get_json()
    assert health["data"]["accessKeyRequired"] is True
    assert health["data"]["maxUploadMb"] == 15

    denied = client.post("/api/notebook/execute", json={"code": "1"})
    assert denied.status_code == 401
    assert denied.get_json()["message"] == "Ingresa la clave del equipo."
    assert client.post(
        "/api/notebook/upload-excel", data={}, content_type="multipart/form-data"
    ).status_code == 401

    wrong = client.post("/api/notebook/execute", json={"code": "1"}, headers={"X-Access-Key": "otra"})
    assert wrong.status_code == 401
    ok = client.post("/api/notebook/execute", json={"code": "1"}, headers={"X-Access-Key": "clave-del-equipo"})
    assert ok.status_code == 200


def test_no_access_key_needed_when_not_configured(client):
    assert client.get("/api/health").get_json()["data"]["accessKeyRequired"] is False
    assert _execute(client, "1").status_code == 200


def test_server_issues_signed_session_and_ignores_client_chosen_ids():
    app = create_app()
    raw = FlaskClient(app, use_cookies=False)  # plain client: no token forwarding
    first = raw.post("/api/notebook/execute", json={"code": "secreto = 41"}, headers={"X-Session-Id": "anonymous"})
    token = first.headers.get("X-Session-Id")
    assert token and token != "anonymous"

    # Same token -> same worker namespace.
    again = raw.post("/api/notebook/execute", json={"code": "secreto + 1"}, headers={"X-Session-Id": token})
    assert again.get_json()["data"]["result_text"] == "42"
    assert again.headers.get("X-Session-Id") is None  # valid token: nothing new issued

    # A guessed/forged id never lands in someone else's session.
    forged = raw.post("/api/notebook/execute", json={"code": "secreto"}, headers={"X-Session-Id": "anonymous"})
    assert forged.get_json()["data"]["error"]["type"] == "NameError"
    assert forged.headers.get("X-Session-Id") not in (None, token)


def test_session_header_is_exposed_through_cors(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:4300"})
    assert "X-Session-Id" in response.headers.get("Access-Control-Expose-Headers", "")


def test_get_secret_prefers_app_config():
    app_secrets.reset_captured_secrets()
    app = create_app()
    app.config["GEMINI_API_KEY"] = "desde-config"
    with app.app_context():
        assert app_secrets.get_secret("GEMINI_API_KEY") == "desde-config"


# --- module import must not evaluate secrets --------------------------------


def test_config_module_has_no_secret_attributes():
    from app import config

    for name in ("SECRET_KEY", "APP_ACCESS_KEY", "GEMINI_API_KEY", "SICO_DB_PASSWORD"):
        assert not hasattr(config.Config, name)


def test_profile_quality_is_returned_on_upload(client):
    rows = [{"Vendedor": "A", "Neto": 10.0}, {"Vendedor": "A", "Neto": 10.0}, {"Vendedor": None, "Neto": -5.0}]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    body = client.post(
        "/api/notebook/upload-excel", data={"file": (buf, "q.xlsx")}, content_type="multipart/form-data"
    ).get_json()
    quality = body["data"]["profile"]["quality"]
    assert quality["duplicateRows"] == 1
    assert quality["totalsRowsRemoved"] == 0
    neto = next(c for c in quality["columns"] if c["name"] == "Neto")
    assert neto["negativeCount"] == 1 and neto["negativeSum"] == -5.0
    vendedor = next(c for c in quality["columns"] if c["name"] == "Vendedor")
    assert vendedor["nullCount"] == 1


# --- Review pass 2 (2026-11-19) -------------------------------------------


def test_direct_builtins_import_call_is_blocked_but_c_internal_imports_work():
    from app.notebook.execution import build_namespace, execute_code

    ns = build_namespace()
    blocked = execute_code("__builtins__['__import__']('os')", ns)
    assert blocked["error"] is not None
    assert "no está permitido" in blocked["error"]["message"]
    # C code importing on the cell's behalf (strftime -> time) keeps working.
    ok = execute_code("import datetime\ndatetime.date(2026, 1, 5).strftime('%Y-%m')", build_namespace())
    assert ok["error"] is None


@pytest.mark.parametrize(
    "code",
    [
        "pd.io.parsers.read_csv('/proc/self/environ')",
        "pd.ExcelFile('x.xlsx')",
        "np.memmap('x.bin')",
        "plt.imread('x.png')",
        "sns.load_dataset('tips')",
    ],
)
def test_io_aliases_by_module_path_are_blocked_in_the_worker(client, code):
    # Through a real worker: install_io_guards() patches the libraries
    # process-wide, so it must never run inside the pytest process.
    error = _execute(client, code).get_json()["data"]["error"]
    assert error is not None and error["type"] == "PermissionError", (code, error)


def test_run_dev_loads_dotenv_only_in_the_main_process():
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1] / "run_dev.py").read_text(encoding="utf-8")
    main_block = source.split('if __name__ == "__main__":', 1)
    assert len(main_block) == 2
    assert "load_dotenv()" not in main_block[0].replace("from dotenv import load_dotenv", "")
    assert "load_dotenv()" in main_block[1]
