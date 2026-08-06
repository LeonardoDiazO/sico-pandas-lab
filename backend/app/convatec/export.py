"""FR-13: build the downloadable Excel from a processed result DataFrame."""
import io

import pandas as pd

# Story 2.2 AC: the exported file itself must carry the "no oficial" label,
# not just the on-screen UI -- an earlier version exported the raw internal
# column name with no disclaimer (found in code review).
COMISION_ILUSTRATIVA_EXPORT_LABEL = "Comision_Ilustrativa (VALOR DE EJEMPLO - NO OFICIAL)"


def _labeled(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={"Comision_Ilustrativa": COMISION_ILUSTRATIVA_EXPORT_LABEL})


def build_output_excel(df: pd.DataFrame) -> io.BytesIO:
    export_df = _labeled(df)
    buf = io.BytesIO()
    export_df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


def preview_rows(df: pd.DataFrame, limit: int) -> dict:
    """A JSON-safe sample of exactly what `build_output_excel` would produce
    (same column labels), so the on-screen preview never drifts from the
    downloaded file. NaN/NaT/Timestamp are not JSON-serializable as-is."""
    export_df = _labeled(df)
    sample = export_df.head(limit)
    rows = [
        {col: (None if pd.isna(v) else (str(v) if isinstance(v, pd.Timestamp) else v)) for col, v in row.items()}
        for row in sample.to_dict(orient="records")
    ]
    return {
        "columns": list(map(str, export_df.columns)),
        "rows": rows,
        "totalRows": int(df.shape[0]),
        "previewRows": len(rows),
    }
