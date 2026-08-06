import pandas as pd

from app.convatec.maestros_resumen import (
    resumen_continence,
    resumen_envios_nacionales,
    resumen_otras_franquicias,
    resumen_repartir,
)
from app.convatec.reference_data import (
    REGLA_1_CONTINENCE_POR_DEPARTAMENTO,
    REGLA_3_ENVIOS_POR_DEPARTAMENTO,
    REPARTIR_REGIONS,
)


def test_resumen_continence_covers_every_hardcoded_departamento():
    resumen = resumen_continence()
    assert len(resumen) == len(REGLA_1_CONTINENCE_POR_DEPARTAMENTO)
    meta = next(r for r in resumen if r["departamento"] == "META")
    assert meta["representante"] == "Sandra Villalba"
    assert meta["grupoVendedor"] == 222


def test_resumen_envios_nacionales_covers_every_hardcoded_departamento():
    resumen = resumen_envios_nacionales()
    assert len(resumen) == len(REGLA_3_ENVIOS_POR_DEPARTAMENTO)


def test_resumen_repartir_includes_continence_and_generic_cundinamarca_separately():
    resumen = resumen_repartir()
    labels = {r["region"] for r in resumen}
    assert any("Regla 1" in label for label in labels)
    assert any("Regla 2/3" in label for label in labels)
    assert len(resumen) == len(REPARTIR_REGIONS)


def test_resumen_otras_franquicias_joins_ciudad_from_convenios_table():
    representantes = pd.DataFrame(
        [{"Convenio": "SALUD TOTAL", "Grupo de vendedores": 45, "Representante": "Katerine Bonilla"}]
    )
    convenios = pd.DataFrame([{"CONVENIO": "SALUD TOTAL", "CIUDAD": "BOGOTA"}])
    resumen = resumen_otras_franquicias(representantes, convenios)
    assert resumen == [
        {"convenio": "SALUD TOTAL", "ciudad": "BOGOTA", "grupoVendedor": 45, "representante": "Katerine Bonilla"}
    ]


def test_resumen_otras_franquicias_handles_convenio_without_ciudad_match():
    representantes = pd.DataFrame(
        [{"Convenio": "CONVENIO SIN CIUDAD", "Grupo de vendedores": 1, "Representante": "X"}]
    )
    convenios = pd.DataFrame([{"CONVENIO": "OTRO CONVENIO", "CIUDAD": "MEDELLIN"}])
    resumen = resumen_otras_franquicias(representantes, convenios)
    assert resumen[0]["ciudad"] is None
