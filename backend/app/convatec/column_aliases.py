"""Normalize known header spelling variants at the API edge before any
pipeline code sees the DataFrame.

FR-1 documents the real report headers with accents ("Código"); the actual
sample files inspected during this build use "Codigo" (no accent) -- other
export runs or report versions could plausibly go either way. A targeted
alias map (not a blanket accent-strip across every header, which risks
renaming an unrelated column into a collision) keeps the pipeline's fixed
column names ("Codigo", "Convenio", "Departamento", "Valor Total", ...)
working regardless of which variant a given upload uses.
"""
import pandas as pd

_ALIASES = {
    "código": "Codigo",
    "codigo": "Codigo",
    "departamento de destino": "Departamento",
    "ciudad de destino": "Departamento",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in df.columns:
        key = str(column).strip().lower()
        if key in _ALIASES and _ALIASES[key] not in df.columns:
            rename_map[column] = _ALIASES[key]
    return df.rename(columns=rename_map) if rename_map else df
