"""Business-rule tables that do NOT come from the uploaded master-tables Excel.

Dev note (discovered while implementing Story 1.3, not covered by the PRD):
the real "Flujo del Proceso..." workbook's "Tables" sheet has clean, re-
uploadable data for PRODUCTO and REPRESENTANTES (Regla 2, convenio-keyed),
but its REPRESENTANTES CONTINACE columns hold the "especialistas" reference
table (Sales Coord/Zone), not the department-keyed table Regla 1 actually
uses -- and it has no Grupo de Vendedor column at all for envios nacionales
(Regla 3). The department-keyed tables for Reglas 1 and 3, the "Repartir"
region splits, and the monthly directrices only exist as narrative/example
data in the workbook's "Asignacion" and "Flujo de proceso" sheets (confirmed
by inspecting the real file), not as a re-parseable master table.

For this demo iteration they are hardcoded here, sourced from the brief's
addendum (_bmad-output/planning-artifacts/briefs/brief-comisiones-convatec-*).
PRD Open Question #1 ("quien mantiene los maestros") already flags that this
needs a real update mechanism once this moves past demo/pilot -- until then,
changing these tables means editing this file.
"""

# Regla 1 -- Continence por Departamento. Cundinamarca/Bogota is NOT listed
# here: it always resolves through REPARTIR_REGIONS["cundinamarca"] instead.
REGLA_1_CONTINENCE_POR_DEPARTAMENTO = {
    "META": (222, "Sandra Villalba"),
    "CESAR": (225, "Danny R. Ramirez"),
    "MAGDALENA": (225, "Danny R. Ramirez"),
    "ATLANTICO": (225, "Danny R. Ramirez"),
    "BOYACA": (232, "Adriana M. Rojas"),
    "TOLIMA": (231, "Victoria E. Garces"),
    "NARINO": (223, "Luisa Fernanda Bonilla"),
    "CALDAS": (231, "Victoria E. Garces"),
    "RISARALDA": (231, "Victoria E. Garces"),
    "HUILA": (231, "Victoria E. Garces"),
    "QUINDIO": (231, "Victoria E. Garces"),
    "VALLE DEL CAUCA": (223, "Luisa Fernanda Bonilla"),
    "CAUCA": (223, "Luisa Fernanda Bonilla"),
    "BOLIVAR": (225, "Danny R. Ramirez"),
    "ANTIOQUIA": (224, "Adriana Granada"),
    "SANTANDER": (229, "Sirley Camacho"),
    "NORTE DE SANTANDER": (229, "Sirley Camacho"),
    "SUCRE": (225, "Danny R. Ramirez"),
    "CORDOBA": (225, "Danny R. Ramirez"),
    "LA GUAJIRA": (225, "Danny R. Ramirez"),
    "ARMENIA": (231, "Victoria E. Garces"),
    "NEIVA": (231, "Victoria E. Garces"),
    "CASANARE": (232, "Adriana M. Rojas"),
    "CHOCO": (224, "Adriana Granada"),
}
REGLA_1_REPARTIR_DEPARTAMENTOS = {"CUNDINAMARCA/BOGOTA", "CUNDINAMARCA", "BOGOTA"}

# Regla 3 -- Envios Nacionales por Departamento destino.
REGLA_3_ENVIOS_POR_DEPARTAMENTO = {
    "META": (199, "Jhoanna Poveda"),
    "CESAR": (55, "Gina Gonzalez"),
    "MAGDALENA": (200, "Esmeralda Livingston"),
    "BOYACA": (136, "Erika Castañeda"),
    "TOLIMA": (49, "Yurey Torres"),
    "NARINO": (169, "Sandra Cortes"),
    "CALDAS": (54, "María Fernanda Ospin"),
    "RISARALDA": (54, "María Fernanda Ospin"),
    "HUILA": (239, "Yurany Aldana"),
    "QUINDIO": (54, "María Fernanda Ospin"),
    "BOLIVAR": (167, "Diana Muñoz"),
    "SANTANDER": (220, "Brisley Lamus"),
    "NORTE DE SANTANDER": (230, "Diana Capacho"),
    "SUCRE": (237, "Ana Carolina Jimenez"),
    "CORDOBA": (237, "Ana Carolina Jimenez"),
    "LA GUAJIRA": (46, "Maria Juliana Velez"),
    "ARMENIA": (54, "María Fernanda Ospin"),
    "NEIVA": (239, "Yurany Aldana"),
    "CASANARE": (136, "Erika Castañeda"),
}
# Departamentos de envios nacionales que resuelven a "Repartir [Region]".
REGLA_3_REPARTIR_POR_DEPARTAMENTO = {
    "ATLANTICO": "costa",
    "VALLE DEL CAUCA": "valle",
    "CAUCA": "valle",
    "ANTIOQUIA": "antioquia",
    "CUNDINAMARCA/BOGOTA": "cundinamarca",
    "CUNDINAMARCA": "cundinamarca",
    "BOGOTA": "cundinamarca",
}

# Caso especial "Repartir [Region]" -- N representantes por region; el split
# proporcional (FR-9) divide cualquier linea que resuelva aqui entre estos N.
# "continence_cundinamarca" es una region distinta de "cundinamarca": Regla 1
# (Continence) reparte Cundinamarca/Bogota entre un par de representantes
# DIFERENTE del que usan Regla 2/3 para la misma region (bug real encontrado
# en code review: antes ambas resolvian al mismo "Repartir Cundinamarca",
# dejando muerta esta tabla y usando el par equivocado para Continence).
REPARTIR_REGIONS = {
    "cundinamarca": [(188, "Angie Lopez"), (59, "Adriana Hernandez")],
    "continence_cundinamarca": [(232, "Adriana M. Rojas"), (222, "Sandra Villalba")],
    "antioquia": [(44, "Ana M. Montes"), (50, "Eryka Gaona")],
    "valle": [(56, "Marlin Celia Daza"), (48, "Luis Alfonso Granobles")],
    "costa": [(200, "Esmeralda Livingston"), (46, "Maria Juliana Velez")],
}
REGLA_1_CUNDINAMARCA_SPLIT = REPARTIR_REGIONS["continence_cundinamarca"]

# Directrices comerciales -- rotacion mensual. Meses impares (1,3,5,...) vs pares.
DIRECTRICES_ROTACION_MENSUAL = {
    "BMC-PARTICULARES": {
        "impar": (188, "Angie Lopez"),
        "par": (59, "Adriana Hernandez"),
    },
    "CONTINENCE PARTICULARES": {
        "impar": (232, "Adriana Marcela Rojas"),
        "par": (222, "Sandra Villalba"),
    },
}

# Distribuciones fijas 50/50, sin importar el mes. Value = key into
# REPARTIR_REGIONS (NOT a representante list directly) so
# app.convatec.pipeline.aplicar_directrices can build a "Repartir <region>"
# marker that split_repartir actually resolves -- pointing at the list
# itself (as an earlier version of this file did) produced a marker string
# ("Repartir CVC MED") that matched no REPARTIR_REGIONS key, so the split
# silently never ran (bug found in code review).
#
# CVC MED/CAL/BAR no traen los pares grupo/representante explicitos en la
# fuente -- se infieren por nomenclatura regional (MED=Antioquia,
# CAL=Valle, BAR=Costa/Barranquilla). Marcado para confirmar con Carlos
# junto con el resto de reglas de Fase 2.
DIRECTRICES_FIJAS_50_50 = {
    "CONTINENCE CUNDINAMARCA": "continence_cundinamarca",
    "CVC MED": "antioquia",
    "CVC CAL": "valle",
    "CVC BAR": "costa",
}


def is_month_odd(month: int) -> bool:
    return month % 2 == 1
