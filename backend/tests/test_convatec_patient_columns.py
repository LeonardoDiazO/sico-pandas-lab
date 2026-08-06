import pandas as pd

from app.convatec.patient_columns import drop_patient_columns


def test_drops_all_known_patient_columns_case_and_accent_insensitive():
    df = pd.DataFrame(
        [
            {
                "Convenio": "COMPENSAR",
                "Paciente": "Jose Perez",
                "Identificación": "123",
                "Género": "M",
                "Fecha de Nacimiento": "1980-01-01",
                "Teléfono Paciente": "555",
                "Celular Paciente": "300",
                "Celular 2 Paciente": "301",
                "Especialidad": "Enfermería",
                "Valor Total": 100.0,
            }
        ]
    )
    result = drop_patient_columns(df)
    assert list(result.columns) == ["Convenio", "Valor Total"]


def test_keeps_non_patient_columns_untouched():
    df = pd.DataFrame([{"Convenio": "X", "Codigo": "1", "Valor Total": 10.0}])
    result = drop_patient_columns(df)
    assert list(result.columns) == ["Convenio", "Codigo", "Valor Total"]
    assert result.iloc[0]["Valor Total"] == 10.0


def test_drops_any_numbered_phone_column_not_just_the_first_two():
    """Real file found during manual review has 'Celular Paciente', 'Celular
    2 Paciente' AND 'Celular 3 Paciente' -- an initial column-list read that
    only looked at the first 20 of 32 real columns missed the third one."""
    df = pd.DataFrame(
        [
            {
                "Celular Paciente": "300",
                "Celular 2 Paciente": "301",
                "Celular 3 Paciente": "302",
                "Telefono 2 Paciente": "303",
                "Convenio": "X",
            }
        ]
    )
    result = drop_patient_columns(df)
    assert list(result.columns) == ["Convenio"]


def test_does_not_drop_convenio_name_or_nit_columns_that_sound_like_phi():
    """'Nombre' and 'Identiificación cliente' hold the CONVENIO's own name/
    NIT in the real file, not the patient's -- must survive."""
    df = pd.DataFrame([{"Nombre": "Compensar", "Identiificación cliente": "860066942", "Convenio": "X"}])
    result = drop_patient_columns(df)
    assert list(result.columns) == ["Nombre", "Identiificación cliente", "Convenio"]
