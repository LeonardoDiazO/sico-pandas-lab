"""Patient-identifying columns that must never survive ingestion.

The real Convatec product/service reports (Sap Report / Dataexportada) carry
patient PHI (name, ID, gender, birth date, phone numbers, specialty) that the
assignment/commission engine never needs -- only Convenio/Codigo/Cantidad/
Valor Total/Fecha matter (PRD S5.2, NFR-2). Dropped by name match, case- and
accent-insensitive, so a header casing difference between the products and
services reports doesn't let PHI slip through.

The real file has "Celular Paciente", "Celular 2 Paciente" AND "Celular 3
Paciente" -- an initial inspection that only looked at the first 20 of the
file's 32 real columns missed the third one entirely (found by running the
actual file through this module, not from the column list alone). A regex
for the numbered-phone-column shape closes this as a class, not one literal
at a time -- there being a "Celular 4 Paciente" tomorrow shouldn't require
another code change.

Columns confirmed NOT patient PHI despite sounding like it: "Nombre" and
"Identiificación cliente" (real column, real typo) hold the CONVENIO's own
commercial name/NIT, not the patient's -- verified against real data before
excluding them from this list, to avoid over-triggering on "nombre" as a
bare keyword (which would drop unrelated columns elsewhere).
"""
import re
import unicodedata

PATIENT_COLUMN_NAMES = {
    "tipo de documento",
    "identificacion",
    "paciente",
    "nombre paciente",
    "nombre del paciente",
    "tipo paciente",
    "genero",
    "sexo",
    "fecha de nacimiento",
    "especialidad",
    "telefono paciente",
    "direccion paciente",
    "email paciente",
    "correo paciente",
}

# Matches "celular paciente", "celular 2 paciente", "celular 3 paciente", ...
# and the same shape for "telefono".
_NUMBERED_PHONE_PATTERN = re.compile(r"^(celular|telefono)( \d+)? paciente$")


def _normalize(name: str) -> str:
    stripped = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    return stripped.strip().lower()


def _is_patient_column(normalized_name: str) -> bool:
    return normalized_name in PATIENT_COLUMN_NAMES or bool(_NUMBERED_PHONE_PATTERN.match(normalized_name))


def drop_patient_columns(df):
    """Return a copy of df with every PHI column removed, whatever the case/accents."""
    to_drop = [c for c in df.columns if _is_patient_column(_normalize(c))]
    return df.drop(columns=to_drop)
