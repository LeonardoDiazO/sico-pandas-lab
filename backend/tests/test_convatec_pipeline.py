import pandas as pd

from app.convatec.pipeline import (
    aplicar_directrices,
    asignar_convenio_ciudad,
    asignar_convenio_regla2,
    asignar_regla1_continence,
    asignar_regla3_envios_nacionales,
    calcular_comision_ilustrativa,
    homologar_productos,
    marcar_excepciones,
    procesar_ciclo,
    split_repartir,
)

PRODUCTO_TABLE = pd.DataFrame(
    [
        {"ICC": "1004113", "Franquicia": "CONTINENCE", "Familia": "Flexiseal", "Clase": "0", "Grupo": "Continence Care", "Clasificación Cuota Producto": "1. CCC"},
        {"ICC": "1002655", "Franquicia": "OSTOMIAS", "Familia": "GNL", "Clase": "0", "Grupo": "Ostomy Care", "Clasificación Cuota Producto": "2. OST"},
    ]
)

REPRESENTANTES_TABLE = pd.DataFrame(
    [
        {"Convenio": "SALUD TOTAL", "Grupo de vendedores": 45, "Representante": "Katerine Bonilla"},
        {"Convenio": "MEDAXA COLPATRIA SEGUROS SA", "Grupo de vendedores": None, "Representante": "Repartir Antioquia"},
    ]
)

CONVENIOS_TABLE = pd.DataFrame(
    [
        {"CONVENIO": "SALUD TOTAL", "CIUDAD": "BOGOTA"},
        {"CONVENIO": "MEDAXA COLPATRIA SEGUROS SA", "CIUDAD": "MEDELLIN"},
    ]
)


def test_homologar_productos_matches_by_icc_not_sap_code():
    """Confirmed against real Convatec files during manual review: the sales
    report's 'Codigo' is HyperSoft's ICC, a different namespace from
    Convatec's own SAP Code (0 matches joining on SAP Code across ~92k real
    rows; 140/388 distinct codes matched joining on ICC)."""
    df = pd.DataFrame([{"Codigo": "1004113", "Valor Total": 100.0}, {"Codigo": "9999999", "Valor Total": 50.0}])
    result = homologar_productos(df, PRODUCTO_TABLE)
    assert result.iloc[0]["Franquicia"] == "CONTINENCE"
    assert result.iloc[0]["Linea_Negocio"] == "Continence Care"
    assert pd.isna(result.iloc[1]["Franquicia"])


def test_homologar_productos_tolerates_numeric_vs_text_icc():
    """A common SAP/Excel export quirk: '1004113' in one file, 1004113.0 in another."""
    producto_table = pd.DataFrame(
        [{"ICC": 1004113.0, "Franquicia": "CONTINENCE", "Familia": "F", "Clase": "0", "Grupo": "G", "Clasificación Cuota Producto": "1"}]
    )
    df = pd.DataFrame([{"Codigo": "1004113", "Valor Total": 100.0}])
    result = homologar_productos(df, producto_table)
    assert result.iloc[0]["Franquicia"] == "CONTINENCE"


def test_asignar_convenio_regla2_direct_and_repartir():
    df = pd.DataFrame(
        [
            {"Convenio": "SALUD TOTAL", "Valor Total": 100.0},
            {"Convenio": "MEDAXA COLPATRIA SEGUROS SA", "Valor Total": 200.0},
        ]
    )
    result = asignar_convenio_regla2(df, REPRESENTANTES_TABLE)
    assert result.iloc[0]["Representante"] == "Katerine Bonilla"
    assert result.iloc[1]["Representante"] == "Repartir Antioquia"


def test_asignar_convenio_ciudad_resolves_ciudad_from_convenio():
    df = pd.DataFrame([{"Convenio": "SALUD TOTAL", "Valor Total": 100.0}])
    result = asignar_convenio_ciudad(df, CONVENIOS_TABLE)
    assert result.iloc[0]["Ciudad"] == "BOGOTA"


def test_asignar_regla1_continence_por_departamento():
    df = pd.DataFrame([{"Departamento": "META", "Valor Total": 100.0}, {"Departamento": "DESCONOCIDO", "Valor Total": 1.0}])
    result = asignar_regla1_continence(df)
    assert result.iloc[0]["Representante"] == "Sandra Villalba"
    assert result.iloc[0]["Grupo_Vendedor"] == 222
    assert pd.isna(result.iloc[1]["Representante"])


def test_asignar_regla1_continence_missing_departamento_column_does_not_crash():
    df = pd.DataFrame([{"Convenio": "X", "Valor Total": 100.0}])
    result = asignar_regla1_continence(df)
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["Representante"])


def test_asignar_regla1_cundinamarca_uses_regla1_specific_pair_after_split():
    """Regla 1's Cundinamarca/Bogota split must use 232/222, NOT the generic
    188/59 pair Regla 2/3 use for the same region (bug found in code review)."""
    df = pd.DataFrame([{"Departamento": "CUNDINAMARCA/BOGOTA", "Valor Total": 100.0}])
    asignado = asignar_regla1_continence(df)
    result = split_repartir(asignado)
    assert set(result["Representante"]) == {"Adriana M. Rojas", "Sandra Villalba"}
    assert result["Valor Total"].sum() == 100.0


def test_asignar_regla3_envios_nacionales_direct_and_repartir():
    df = pd.DataFrame(
        [
            {"Departamento": "META", "Valor Total": 100.0},
            {"Departamento": "ANTIOQUIA", "Valor Total": 100.0},
        ]
    )
    result = asignar_regla3_envios_nacionales(df)
    assert result.iloc[0]["Representante"] == "Jhoanna Poveda"
    assert result.iloc[1]["Representante"] == "Repartir antioquia"


def test_split_repartir_sum_is_exact_and_n_is_not_hardcoded():
    df = pd.DataFrame([{"Representante": "Repartir antioquia", "Valor Total": 100.0, "Convenio": "X"}])
    result = split_repartir(df)
    assert len(result) == 2  # REPARTIR_REGIONS["antioquia"] has 2 members today
    assert result["Valor Total"].sum() == 100.0
    assert set(result["Representante"]) == {"Ana M. Montes", "Eryka Gaona"}


def test_split_repartir_case_insensitive_prefix_match():
    df = pd.DataFrame([{"Representante": "REPARTIR ANTIOQUIA", "Valor Total": 100.0, "Convenio": "X"}])
    result = split_repartir(df)
    assert len(result) == 2


def test_split_repartir_exact_sum_for_n_that_does_not_divide_evenly():
    """FR-9's exact-sum guarantee must hold for any N, not just N=2 (bug found in code review)."""
    df = pd.DataFrame([{"Representante": "Repartir tresvias", "Valor Total": 100.0, "Convenio": "X"}])
    import app.convatec.reference_data as ref

    ref.REPARTIR_REGIONS["tresvias"] = [(1, "A"), (2, "B"), (3, "C")]
    try:
        result = split_repartir(df)
        assert len(result) == 3
        assert result["Valor Total"].sum() == 100.0
    finally:
        del ref.REPARTIR_REGIONS["tresvias"]


def test_split_repartir_unmapped_region_leaves_representante_unresolved_not_garbage_string():
    df = pd.DataFrame([{"Representante": "Repartir Region Inexistente", "Valor Total": 100.0, "Convenio": "X"}])
    result = split_repartir(df)
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["Representante"])  # never leaks the raw marker string


def test_split_repartir_leaves_direct_assignments_untouched():
    df = pd.DataFrame([{"Representante": "Katerine Bonilla", "Valor Total": 50.0, "Convenio": "SALUD TOTAL"}])
    result = split_repartir(df)
    assert len(result) == 1
    assert result.iloc[0]["Valor Total"] == 50.0


def test_aplicar_directrices_alternates_by_month_parity():
    df = pd.DataFrame([{"Convenio": "BMC-PARTICULARES", "Valor Total": 10.0}])
    odd = aplicar_directrices(df, mes=1)
    even = aplicar_directrices(df, mes=2)
    assert odd.iloc[0]["Representante"] == "Angie Lopez"
    assert even.iloc[0]["Representante"] == "Adriana Hernandez"


def test_aplicar_directrices_fijas_50_50_actually_splits():
    """CVC MED/CAL/BAR must resolve to a real REPARTIR_REGIONS key and
    actually split, not leak an unmatched 'Repartir CVC MED' string (bug
    found in code review)."""
    df = pd.DataFrame([{"Convenio": "CVC MED", "Valor Total": 100.0}])
    con_directriz = aplicar_directrices(df, mes=1)
    result = split_repartir(con_directriz)
    assert len(result) == 2
    assert set(result["Representante"]) == {"Ana M. Montes", "Eryka Gaona"}
    assert result["Valor Total"].sum() == 100.0


def test_marcar_excepciones_flags_unhomologated_product_without_dropping_row():
    df = pd.DataFrame([{"Franquicia": None, "Convenio": "X", "Representante": None, "Origen": "producto"}])
    result = marcar_excepciones(df)
    assert len(result) == 1
    assert result.iloc[0]["Motivo_Excepcion"] == "producto sin homologar"


def test_marcar_excepciones_does_not_flag_envios_nacionales_as_unhomologated():
    """Envios nacionales never goes through homologar_productos, so it has
    no Franquicia column of its own -- concatenating with productos/servicios
    must not make every envio line look 'sin homologar' (bug found in code review)."""
    df = pd.DataFrame(
        [
            {"Franquicia": None, "Convenio": None, "Representante": "Jhoanna Poveda", "Origen": "envio_nacional"},
            {"Franquicia": None, "Convenio": "X", "Representante": None, "Origen": "producto"},
        ]
    )
    result = marcar_excepciones(df)
    assert pd.isna(result.iloc[0]["Motivo_Excepcion"])
    assert result.iloc[1]["Motivo_Excepcion"] == "producto sin homologar"


def test_marcar_excepciones_flags_unknown_convenio():
    df = pd.DataFrame([{"Franquicia": "OSTOMIAS", "Convenio": "NUEVO CONVENIO", "Representante": None, "Origen": "producto"}])
    result = marcar_excepciones(df)
    assert result.iloc[0]["Motivo_Excepcion"] == "convenio nuevo sin representante"


def test_marcar_excepciones_continence_without_departamento_is_not_mislabeled_as_convenio():
    """A Continence line resolves via Departamento (Regla 1), never via
    Convenio -- must be flagged 'ciudad sin asignación', not 'convenio
    nuevo sin representante' (bug found in code review)."""
    df = pd.DataFrame(
        [{"Franquicia": "CONTINENCE", "Convenio": "ALGUN CONVENIO", "Representante": None, "Origen": "producto"}]
    )
    result = marcar_excepciones(df)
    assert result.iloc[0]["Motivo_Excepcion"] == "ciudad sin asignación"


def test_marcar_excepciones_generates_output_even_with_marked_lines():
    df = pd.DataFrame(
        [
            {"Franquicia": None, "Convenio": "X", "Representante": None, "Origen": "producto"},
            {"Franquicia": "OSTOMIAS", "Convenio": "SALUD TOTAL", "Representante": "Katerine Bonilla", "Origen": "producto"},
        ]
    )
    result = marcar_excepciones(df)
    assert len(result) == 2  # never blocks / drops rows


def test_calcular_comision_ilustrativa_divides_by_distinct_grupo_vendedor_in_sede():
    """Must count by Grupo_Vendedor, not by Representante name -- the same
    person spelled two ways in the source data must not inflate the
    denominator (bug found in code review)."""
    df = pd.DataFrame(
        [
            {"Departamento": "META", "Grupo_Vendedor": 222, "Representante": "Sandra Villalba", "Convenio": None},
            {"Departamento": "META", "Grupo_Vendedor": 222, "Representante": "Sandra  Villalba", "Convenio": None},
            {"Departamento": "META", "Grupo_Vendedor": 999, "Representante": "Otro Rep", "Convenio": None},
        ]
    )
    result = calcular_comision_ilustrativa(df, valor_referencia=100.0)
    assert result["Comision_Ilustrativa"].tolist() == [50.0, 50.0, 50.0]


def test_calcular_comision_ilustrativa_skips_rows_without_representante():
    df = pd.DataFrame([{"Departamento": "META", "Grupo_Vendedor": None, "Representante": None, "Convenio": None}])
    result = calcular_comision_ilustrativa(df, valor_referencia=100.0)
    assert result.iloc[0]["Comision_Ilustrativa"] is None


def test_calcular_comision_ilustrativa_missing_departamento_column_does_not_crash():
    df = pd.DataFrame([{"Convenio": "SALUD TOTAL", "Grupo_Vendedor": 45, "Representante": "Katerine Bonilla"}])
    result = calcular_comision_ilustrativa(df, valor_referencia=100.0)
    assert result.iloc[0]["Comision_Ilustrativa"] == 100.0


def test_procesar_ciclo_end_to_end_combines_sources_and_marks_exceptions():
    productos = pd.DataFrame(
        [
            {"Codigo": "1004113", "Convenio": "X", "Departamento": "META", "Valor Total": 100.0},
            {"Codigo": "1002655", "Convenio": "SALUD TOTAL", "Departamento": None, "Valor Total": 50.0},
        ]
    )
    resultado = procesar_ciclo(
        productos=productos,
        servicios=None,
        envios_nacionales=None,
        producto_table=PRODUCTO_TABLE,
        representantes_table=REPRESENTANTES_TABLE,
        convenios_table=CONVENIOS_TABLE,
        mes=3,
    )
    assert len(resultado) == 2
    assert set(resultado["Origen"]) == {"producto"}
    continence_row = resultado[resultado["Departamento"] == "META"].iloc[0]
    assert continence_row["Representante"] == "Sandra Villalba"
    ostomias_row = resultado[resultado["Convenio"] == "SALUD TOTAL"].iloc[0]
    assert ostomias_row["Representante"] == "Katerine Bonilla"
    assert ostomias_row["Ciudad"] == "BOGOTA"


def test_procesar_ciclo_with_all_three_sources_does_not_flag_envios_as_unhomologated():
    productos = pd.DataFrame([{"Codigo": "1004113", "Convenio": "X", "Departamento": "META", "Valor Total": 100.0}])
    envios = pd.DataFrame([{"Departamento": "META", "Valor Total": 20.0}])
    resultado = procesar_ciclo(
        productos=productos,
        servicios=None,
        envios_nacionales=envios,
        producto_table=PRODUCTO_TABLE,
        representantes_table=REPRESENTANTES_TABLE,
        convenios_table=CONVENIOS_TABLE,
        mes=3,
    )
    envio_row = resultado[resultado["Origen"] == "envio_nacional"].iloc[0]
    assert pd.isna(envio_row["Motivo_Excepcion"])


def test_procesar_ciclo_raises_when_no_ventas_loaded():
    try:
        procesar_ciclo(None, None, None, PRODUCTO_TABLE, REPRESENTANTES_TABLE, CONVENIOS_TABLE, mes=1)
        assert False, "expected ValueError"
    except ValueError:
        pass
