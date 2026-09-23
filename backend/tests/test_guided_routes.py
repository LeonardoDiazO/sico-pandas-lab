import io
import re

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


@pytest.mark.parametrize("lesson_id", ["01-fundamentos", "03-agrupar", "05-graficas"])
def test_every_synthetic_identifier_in_static_content_has_a_declared_role(lesson_id):
    """Regression: the actual root cause of the bug below - lesson 1's
    step 1.2 static synthetic table had a FOURTH key ("mov_cia") that was
    never added to data_context.LESSON_ROLES's role mapping in the first
    place. Comparing the identifiers LESSON_ROLES claims to know about
    against what content.py's STATIC (no-profile) code actually contains is
    what would have caught this - a test that only inspects DYNAMIC output
    can't, since an unmapped identifier is by definition invisible to it."""
    from app.guided import content, data_context

    static_lesson = content.get_lesson(lesson_id)
    full_text = "\n".join(step["code"] for step in static_lesson["steps"])
    if static_lesson["challenge"]:
        full_text += static_lesson["challenge"]["prompt"]

    identifiers_in_code = set(re.findall(r"'(mov_\w+)'", full_text))
    roles = data_context.LESSON_ROLES[lesson_id]
    mapped_identifiers = {v for k, v in roles.items() if k != "table_var_default"}

    assert identifiers_in_code == mapped_identifiers, (
        f"{lesson_id}: static content uses {identifiers_in_code} but "
        f"LESSON_ROLES only maps {mapped_identifiers} - every synthetic "
        "column the static example creates must have a role, or it leaks "
        "through unsubstituted once a learner's own data activates dynamic "
        "content."
    )


@pytest.mark.parametrize("lesson_id", ["01-fundamentos", "03-agrupar", "05-graficas"])
def test_dynamic_lesson_never_leaves_an_unsubstituted_synthetic_identifier(client, lesson_id):
    """Regression: a real bug seen live - lesson 1's step 1.2 synthetic table
    had a FOURTH key ("mov_cia") nobody ever mapped to a role in
    data_context.LESSON_ROLES (only mov_item/mov_cantidad/mov_neto were).
    With a context active, substitute_identifiers() replaced the three
    mapped identifiers but silently left "mov_cia" untouched - a learner
    who'd uploaded their OWN file saw a column name they never gave the
    system, mixed in with their real ones, in their own bound `df`. This
    blanket check - none of a lesson's known synthetic identifiers may
    survive substitution once a context resolves - would have caught it
    immediately, and guards every in-scope lesson against the same mistake
    creeping back in (e.g. someone editing content.py's synthetic table
    without updating LESSON_ROLES to match)."""
    from app.guided import data_context

    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.get(f"/api/guided/lessons/{lesson_id}")
    data = response.get_json()["data"]

    roles = data_context.LESSON_ROLES[lesson_id]
    synthetic_identifiers = {roles["table_var_default"]} | {v for k, v in roles.items() if k != "table_var_default"}

    full_text = "\n".join(step["code"] + step["explanation"] for step in data["steps"])
    if data["challenge"]:
        full_text += data["challenge"]["prompt"]

    for identifier in synthetic_identifiers:
        assert identifier not in full_text, f"'{identifier}' leaked into dynamic content for {lesson_id}"


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


def test_lessons_list_without_any_upload_marks_all_six_as_synthetic(client):
    response = client.get("/api/guided/lessons")
    lessons = response.get_json()["data"]["lessons"]
    assert len(lessons) == 6
    assert all(lesson["usa_datos_reales"] is False for lesson in lessons)


def test_lessons_list_without_x_session_id_header_does_not_error(client):
    """No X-Session-Id header -> _session_id() falls back to "anonymous",
    an unknown session for get_known_profile() -> same as no profile at
    all: no error, every lesson reports usa_datos_reales: false."""
    response = client.get("/api/guided/lessons")
    assert response.status_code == 200
    lessons = response.get_json()["data"]["lessons"]
    assert all(lesson["usa_datos_reales"] is False for lesson in lessons)


def test_lessons_list_after_uploading_sufficient_profile_marks_eligible_lessons_true(client):
    client.post(
        "/api/notebook/upload-excel",
        data={"file": (_own_xlsx_bytes(), "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.get("/api/guided/lessons")
    lessons = {lesson["id"]: lesson["usa_datos_reales"] for lesson in response.get_json()["data"]["lessons"]}

    # In LESSON_ROLES, sufficient profile -> True.
    assert lessons["01-fundamentos"] is True
    assert lessons["03-agrupar"] is True
    assert lessons["05-graficas"] is True
    # Never in LESSON_ROLES -> always False, even with a sufficient profile.
    assert lessons["00-python-desde-cero"] is False
    assert lessons["02-filtrar-ordenar"] is False
    assert lessons["04-combinar-tablas"] is False


def test_lessons_list_with_insufficient_profile_keeps_eligible_lessons_false(client):
    """01-fundamentos/03-agrupar need 2 distinct numeric columns and 1
    categorical column; a profile with only a single numeric column can't
    fill both num1/num2 roles, so resolve_context() must return None for
    them (05-graficas only needs one numeric column, so it stays eligible)."""
    rows = [{"Vendedor": v, "Cantidad": c} for v, c in [("Ana", 3), ("Luis", 1), ("Ana", 5), ("Marta", 2)]]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)

    client.post(
        "/api/notebook/upload-excel",
        data={"file": (buf, "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.get("/api/guided/lessons")
    lessons = {lesson["id"]: lesson["usa_datos_reales"] for lesson in response.get_json()["data"]["lessons"]}

    assert lessons["01-fundamentos"] is False
    assert lessons["03-agrupar"] is False
    assert lessons["05-graficas"] is True


def test_lessons_list_with_no_categorical_column_keeps_all_eligible_lessons_false(client):
    """01-fundamentos/03-agrupar/05-graficas all need a categorical column
    (the `cat` role) - a profile that's all-numeric (no categorical column
    at all) must fail resolve_context() for every one of them, not just the
    two-numeric-columns case already covered above."""
    rows = [{"Cantidad": c, "Neto": n} for c, n in [(3, 30000), (1, 12000), (5, 50000), (2, 8000)]]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)

    client.post(
        "/api/notebook/upload-excel",
        data={"file": (buf, "ventas.xlsx")},
        content_type="multipart/form-data",
    )

    response = client.get("/api/guided/lessons")
    lessons = {lesson["id"]: lesson["usa_datos_reales"] for lesson in response.get_json()["data"]["lessons"]}

    assert lessons["01-fundamentos"] is False
    assert lessons["03-agrupar"] is False
    assert lessons["05-graficas"] is False


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
