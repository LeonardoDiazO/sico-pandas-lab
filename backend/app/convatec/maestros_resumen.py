"""Read-only, human-readable directory of sede/ciudad/representante coverage.

Story request (2026-08-06): a screen the user can show in the Convatec
meeting on its own, separate from the sell-out processing flow -- "here is
our full territory map" -- built from the same reference data and uploaded
master tables the assignment engine (pipeline.py) already uses, never a
second source of truth.
"""
import pandas as pd

from app.convatec.normalize import norm as _norm
from app.convatec.reference_data import (
    REGLA_1_CONTINENCE_POR_DEPARTAMENTO,
    REGLA_3_ENVIOS_POR_DEPARTAMENTO,
    REPARTIR_REGIONS,
)

# Human-facing labels for the two hardcoded Cundinamarca/Bogota special cases
# already in reference_data.py -- see that module's docstring for why they
# are hardcoded rather than parsed from the uploaded workbook.
_REGION_LABELS = {
    "cundinamarca": "Repartir Cundinamarca (Regla 2/3)",
    "continence_cundinamarca": "Repartir Cundinamarca (Regla 1 - Continence)",
    "antioquia": "Repartir Antioquia",
    "valle": "Repartir Valle",
    "costa": "Repartir Costa",
}


def _regla_departamento(tabla: dict) -> list[dict]:
    return [
        {"departamento": depto, "grupoVendedor": grupo, "representante": rep}
        for depto, (grupo, rep) in sorted(tabla.items())
    ]


def resumen_continence() -> list[dict]:
    return _regla_departamento(REGLA_1_CONTINENCE_POR_DEPARTAMENTO)


def resumen_envios_nacionales() -> list[dict]:
    return _regla_departamento(REGLA_3_ENVIOS_POR_DEPARTAMENTO)


def resumen_repartir() -> list[dict]:
    return [
        {
            "region": _REGION_LABELS.get(region, region),
            "miembros": [{"grupoVendedor": grupo, "representante": rep} for grupo, rep in miembros],
        }
        for region, miembros in REPARTIR_REGIONS.items()
    ]


def resumen_otras_franquicias(representantes_table: pd.DataFrame, convenios_table: pd.DataFrame) -> list[dict]:
    """Regla 2 -- every direct Convenio -> Representante assignment, enriched
    with Ciudad from the CONVENIOS master table when available. "Repartir"
    markers are kept as-is (already covered by resumen_repartir())."""
    convenios_lookup = convenios_table[["CONVENIO", "CIUDAD"]].copy()
    convenios_lookup["_norm"] = convenios_lookup["CONVENIO"].map(_norm)
    convenios_lookup = convenios_lookup.drop_duplicates(subset="_norm", keep="first")

    reps = representantes_table[["Convenio", "Grupo de vendedores", "Representante"]].copy()
    reps["_norm"] = reps["Convenio"].map(_norm)
    merged = reps.merge(convenios_lookup.drop(columns="CONVENIO"), on="_norm", how="left")

    return [
        {
            "convenio": row["Convenio"],
            "ciudad": row["CIUDAD"] if pd.notna(row["CIUDAD"]) else None,
            "grupoVendedor": row["Grupo de vendedores"] if pd.notna(row["Grupo de vendedores"]) else None,
            "representante": row["Representante"],
        }
        for _, row in merged.iterrows()
    ]
