"""Shared accent/case-insensitive key normalization -- used by pipeline.py
for merge keys and maestros_resumen.py for the same Convenio/Departamento
joins, so both stay guaranteed consistent (a divergence here would silently
break the maestros view's numbers relative to what the assignment engine
actually resolves)."""
import re
import unicodedata

import pandas as pd

_TRAILING_ZERO_DECIMAL = re.compile(r"\.0+$")


def norm(value) -> str:
    """Normalize a lookup key: accent/case-insensitive, and tolerant of a
    numeric Excel export turning '1004113' into '1004113.0' (SAP Code /
    Convenio codes are sometimes numeric in one file and text in another)."""
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = _TRAILING_ZERO_DECIMAL.sub("", text.strip())
    return text.upper()
