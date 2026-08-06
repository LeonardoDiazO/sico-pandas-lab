"""FR-13: build the downloadable Excel from a processed result DataFrame."""
import io

import pandas as pd

# Story 2.2 AC: the exported file itself must carry the "no oficial" label,
# not just the on-screen UI -- an earlier version exported the raw internal
# column name with no disclaimer (found in code review).
COMISION_ILUSTRATIVA_EXPORT_LABEL = "Comision_Ilustrativa (VALOR DE EJEMPLO - NO OFICIAL)"


def build_output_excel(df: pd.DataFrame) -> io.BytesIO:
    export_df = df.rename(columns={"Comision_Ilustrativa": COMISION_ILUSTRATIVA_EXPORT_LABEL})
    buf = io.BytesIO()
    export_df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf
