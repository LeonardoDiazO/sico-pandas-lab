"""Assignment engine: homologacion -> asignacion de representante -> excepciones.

Column names used throughout this module are the ones this pipeline adds
(Franquicia, Grupo_Vendedor, Representante, Sede, Motivo_Excepcion, ...).
Incoming column names are normalized at the API edge by
`app.convatec.column_aliases` before reaching this module, so everything
here can assume the canonical unaccented names (Codigo, Convenio, ...).

`[ASSUMPTION]` (PRD S10): the envios-nacionales report carries its own
`Departamento` column already (a shipment naturally has a destination). The
products/services reports do NOT carry Departamento -- Continence lines from
those two sources only get a representative when the caller attaches one
(there is no verified Convenio -> Ciudad -> Departamento chain for Regla 1;
FR-5's Convenio -> Ciudad resolution below is a DIFFERENT, verified chain
that does not reach Departamento). Otherwise Continence lines without a
Departamento are marked as an exception (FR-11) rather than guessed.
"""
import pandas as pd

from app.convatec.normalize import norm as _norm
from app.convatec.reference_data import (
    DIRECTRICES_FIJAS_50_50,
    DIRECTRICES_ROTACION_MENSUAL,
    REGLA_1_CONTINENCE_POR_DEPARTAMENTO,
    REGLA_1_REPARTIR_DEPARTAMENTOS,
    REGLA_3_ENVIOS_POR_DEPARTAMENTO,
    REGLA_3_REPARTIR_POR_DEPARTAMENTO,
    REPARTIR_REGIONS,
    is_month_odd,
)

REPARTIR_PREFIX = "Repartir "
CONTINENCE_FRANQUICIA = "CONTINENCE"
CONTINENCE_CUNDINAMARCA_REGION = "continence_cundinamarca"


def _require_columns(df: pd.DataFrame, columns, table_label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"La tabla {table_label} no tiene las columnas esperadas: {', '.join(missing)}"
        )


def _series_or_nan(df: pd.DataFrame, column: str) -> pd.Series:
    """`df.get(column)` returns a 0-length Series when the column is
    entirely absent, which misaligns with df.index -- assigning it back
    (or iterating it) crashes instead of leaving every row unresolved as
    FR-11 requires. This returns a NaN column aligned to df's own index."""
    if column in df.columns:
        return df[column]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def _drop_if_present(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Guards a `merge` against silently producing pandas' `_x`/`_y` suffixes
    if the raw report already has a column with the same name this step is
    about to introduce (e.g. a report that already has a "Ciudad" column of
    its own) -- pandas would otherwise rename both instead of raising, and
    every later step referencing the bare name would silently read the wrong
    one (risk found in code review, no real report is known to hit this, but
    the guard is cheap)."""
    present = [c for c in columns if c in df.columns]
    return df.drop(columns=present) if present else df


def homologar_productos(df: pd.DataFrame, producto_table: pd.DataFrame) -> pd.DataFrame:
    """FR-4: enrich each line with Franquicia/Familia/Clase/Linea de negocio/
    Clasificacion Cuota, joining on ICC -- NOT "SAP Code". Verified against
    the real files during manual review: the sales report's "Codigo" is
    HyperSoft's own ICC code, a different namespace from Convatec's SAP Code
    (0 matches joining on SAP Code across ~92k real rows; 140/388 distinct
    codes matched joining on ICC instead). "Grupo" in the master table is
    Convatec's business-line grouping right after Franquicia -- mapped to
    Linea_Negocio since the real workbook has no column literally named
    "Línea de negocio"."""
    _require_columns(
        producto_table,
        ["ICC", "Franquicia", "Familia", "Clase", "Grupo", "Clasificación Cuota Producto"],
        "PRODUCTO",
    )
    lookup = producto_table[
        ["ICC", "Franquicia", "Familia", "Clase", "Grupo", "Clasificación Cuota Producto"]
    ].rename(columns={"Grupo": "Linea_Negocio", "Clasificación Cuota Producto": "Clasificacion_Cuota"})
    lookup["_sap_code_norm"] = lookup["ICC"].map(_norm)
    lookup = lookup[lookup["_sap_code_norm"] != ""]
    lookup = lookup.drop_duplicates(subset="_sap_code_norm", keep="first")

    out = _drop_if_present(df, ["Franquicia", "Familia", "Clase", "Linea_Negocio", "Clasificacion_Cuota"]).copy()
    out["_codigo_norm"] = _series_or_nan(out, "Codigo").map(_norm)
    out = out.merge(
        lookup.drop(columns="ICC"),
        left_on="_codigo_norm",
        right_on="_sap_code_norm",
        how="left",
    )
    return out.drop(columns=["_codigo_norm", "_sap_code_norm"])


def asignar_convenio_regla2(df: pd.DataFrame, representantes_table: pd.DataFrame) -> pd.DataFrame:
    """FR-7: Regla 2 -- representante por Convenio -> Grupo de vendedores, for non-Continence lines."""
    _require_columns(representantes_table, ["Convenio", "Grupo de vendedores", "Representante"], "REPRESENTANTES")
    lookup = representantes_table[["Convenio", "Grupo de vendedores", "Representante"]].rename(
        columns={"Grupo de vendedores": "Grupo_Vendedor"}
    )
    lookup["_convenio_norm"] = lookup["Convenio"].map(_norm)
    lookup = lookup[lookup["_convenio_norm"] != ""]
    lookup = lookup.drop_duplicates(subset="_convenio_norm", keep="first")

    out = _drop_if_present(df, ["Grupo_Vendedor", "Representante"]).copy()
    out["_convenio_norm"] = _series_or_nan(out, "Convenio").map(_norm)
    out = out.merge(lookup.drop(columns="Convenio"), on="_convenio_norm", how="left")
    return out.drop(columns="_convenio_norm")


def asignar_convenio_ciudad(df: pd.DataFrame, convenios_table: pd.DataFrame) -> pd.DataFrame:
    """FR-5: resolve Ciudad for each line from the CONVENIOS master table
    (Convenio -> Ciudad). This is a separate, verified lookup from Regla 1's
    Departamento resolution -- CONVENIOS has no Departamento column, only
    Ciudad, so it cannot feed Regla 1 (see module docstring)."""
    _require_columns(convenios_table, ["CONVENIO", "CIUDAD"], "CONVENIOS")
    lookup = convenios_table[["CONVENIO", "CIUDAD"]].rename(columns={"CIUDAD": "Ciudad"})
    lookup["_convenio_norm"] = lookup["CONVENIO"].map(_norm)
    lookup = lookup[lookup["_convenio_norm"] != ""]
    lookup = lookup.drop_duplicates(subset="_convenio_norm", keep="first")

    out = _drop_if_present(df, ["Ciudad"]).copy()
    out["_convenio_norm"] = _series_or_nan(out, "Convenio").map(_norm)
    out = out.merge(lookup.drop(columns="CONVENIO"), on="_convenio_norm", how="left")
    return out.drop(columns="_convenio_norm")


def _regla1_lookup(departamento_norm: str):
    if departamento_norm in REGLA_1_REPARTIR_DEPARTAMENTOS:
        return REPARTIR_PREFIX + CONTINENCE_CUNDINAMARCA_REGION
    return REGLA_1_CONTINENCE_POR_DEPARTAMENTO.get(departamento_norm)  # tuple, or None if unknown


def asignar_regla1_continence(df: pd.DataFrame) -> pd.DataFrame:
    """FR-6: Regla 1 -- Continence por Departamento, including the Cundinamarca/Bogota split."""
    out = df.copy()
    grupos, reps = [], []
    for depto in _series_or_nan(out, "Departamento").map(_norm):
        result = _regla1_lookup(depto)
        if result is None:
            grupos.append(None)
            reps.append(None)
        elif isinstance(result, str):  # "Repartir continence_cundinamarca" marker
            grupos.append(None)
            reps.append(result)
        else:
            grupo, rep = result
            grupos.append(grupo)
            reps.append(rep)
    out["Grupo_Vendedor"] = grupos
    out["Representante"] = reps
    return out


def asignar_regla3_envios_nacionales(df: pd.DataFrame) -> pd.DataFrame:
    """FR-8: Regla 3 -- envios nacionales por Departamento destino."""
    out = df.copy()
    grupos, reps = [], []
    for depto in _series_or_nan(out, "Departamento").map(_norm):
        if depto in REGLA_3_REPARTIR_POR_DEPARTAMENTO:
            region = REGLA_3_REPARTIR_POR_DEPARTAMENTO[depto]
            grupos.append(None)
            reps.append(REPARTIR_PREFIX + region)
        elif depto in REGLA_3_ENVIOS_POR_DEPARTAMENTO:
            grupo, rep = REGLA_3_ENVIOS_POR_DEPARTAMENTO[depto]
            grupos.append(grupo)
            reps.append(rep)
        else:
            grupos.append(None)
            reps.append(None)
    out["Grupo_Vendedor"] = grupos
    out["Representante"] = reps
    return out


def _distribute_exact(total: float, n: int) -> list[float]:
    """FR-9: n shares whose sum is exactly `total`, rounded to cents. Plain
    `total / n` can miss the target by a cent or more for n that isn't a
    power of 2 (n=3, e.g.) under IEEE-754 rounding -- the remainder after
    rounding every share down is added to the first share instead of lost."""
    base = round(total / n, 2)
    shares = [base] * n
    remainder = round(total - base * n, 2)
    if remainder:
        shares[0] = round(shares[0] + remainder, 2)
    return shares


def split_repartir(df: pd.DataFrame, valor_col: str = "Valor Total") -> pd.DataFrame:
    """FR-9: expand every "Repartir [Region]" line into N proportional lines.

    The split is exact (sum of the N lines == original value, for any N -- see
    _distribute_exact) and reads N from REPARTIR_REGIONS at call time, so a
    future region-membership change never needs a code change. A "Repartir"
    marker whose region isn't registered is left UNRESOLVED (Representante
    set to None, not the raw marker string) so FR-11's existing "no
    representante" check flags it instead of leaking an invalid name into
    the exported Excel.
    """
    representante = df["Representante"].astype(str)
    is_repartir = representante.str.upper().str.startswith(REPARTIR_PREFIX.upper()) & df["Representante"].notna()
    direct = df.loc[~is_repartir].copy()
    to_split = df.loc[is_repartir]

    expanded_rows = []
    for _, row in to_split.iterrows():
        region_name = str(row["Representante"])[len(REPARTIR_PREFIX):].strip().lower()
        members = REPARTIR_REGIONS.get(region_name, [])
        n = len(members)
        if n == 0:
            unresolved = row.to_dict()
            unresolved["Grupo_Vendedor"] = None
            unresolved["Representante"] = None
            expanded_rows.append(unresolved)
            continue
        shares = _distribute_exact(float(row[valor_col]), n)
        for (grupo, representante_nombre), share in zip(members, shares):
            new_row = row.to_dict()
            new_row[valor_col] = share
            new_row["Grupo_Vendedor"] = grupo
            new_row["Representante"] = representante_nombre
            expanded_rows.append(new_row)

    expanded = pd.DataFrame(expanded_rows) if expanded_rows else df.iloc[0:0].copy()
    return pd.concat([direct, expanded], ignore_index=True)


def aplicar_directrices(df: pd.DataFrame, mes: int) -> pd.DataFrame:
    """FR-10: monthly-rotating and fixed-50/50 commercial directives override
    whatever Regla 1/2/3 resolved for the matching Convenio."""
    out = df.copy()
    out["_convenio_norm"] = _series_or_nan(out, "Convenio").map(_norm)

    for concepto, months in DIRECTRICES_ROTACION_MENSUAL.items():
        grupo, rep = months["impar"] if is_month_odd(mes) else months["par"]
        mask = out["_convenio_norm"] == _norm(concepto)
        out.loc[mask, "Grupo_Vendedor"] = grupo
        out.loc[mask, "Representante"] = rep

    for concepto, region_key in DIRECTRICES_FIJAS_50_50.items():
        mask = out["_convenio_norm"] == _norm(concepto)
        if mask.any():
            out.loc[mask, "Representante"] = REPARTIR_PREFIX + region_key

    return out.drop(columns="_convenio_norm")


def marcar_excepciones(df: pd.DataFrame) -> pd.DataFrame:
    """FR-11: mark, never block. Every line keeps its row; unresolved ones get a reason."""
    out = df.copy()
    motivos = pd.Series([None] * len(out), index=out.index, dtype=object)
    origen = out.get("Origen", pd.Series([""] * len(out), index=out.index))
    es_continence = _series_or_nan(out, "Franquicia").map(_norm) == CONTINENCE_FRANQUICIA

    # Envios nacionales never goes through homologar_productos (Regla 3 keys
    # on Departamento, not Codigo) -- it has no Franquicia column at all, so
    # this check must not apply to it (bug found in code review: every
    # envios-nacionales line was being flagged "producto sin homologar").
    aplica_homologacion = origen != "envio_nacional"
    if "Franquicia" in out.columns:
        sin_homologar = out["Franquicia"].isna() & aplica_homologacion
        motivos = motivos.mask(sin_homologar, "producto sin homologar")

    # Continence resolves via Departamento (Regla 1), never via Convenio --
    # a Continence line missing its department must not be mislabeled as a
    # convenio problem (bug found in code review).
    if "Convenio" in out.columns:
        sin_convenio = (
            out["Representante"].isna() & motivos.isna() & out["Convenio"].notna() & ~es_continence
        )
        motivos = motivos.mask(sin_convenio, "convenio nuevo sin representante")

    sin_departamento = es_continence & out["Representante"].isna() & motivos.isna()
    motivos = motivos.mask(sin_departamento, "ciudad sin asignación")

    duplicated = out.duplicated(keep="first") & motivos.isna()
    motivos = motivos.mask(duplicated, "duplicado")

    out["Motivo_Excepcion"] = motivos
    return out


def _procesar_productos_o_servicios(
    df: pd.DataFrame, producto_table, representantes_table, convenios_table
) -> pd.DataFrame:
    """FR-4, FR-5, FR-6, FR-7: homologar, resolver convenio/ciudad, then split
    Continence (Regla 1) from the rest (Regla 2) before recombining -- each
    row uses exactly one representante rule, never both."""
    homologado = homologar_productos(df, producto_table)
    homologado = asignar_convenio_ciudad(homologado, convenios_table)
    es_continence = _series_or_nan(homologado, "Franquicia").map(_norm) == CONTINENCE_FRANQUICIA

    continence = asignar_regla1_continence(homologado.loc[es_continence])
    resto = asignar_convenio_regla2(homologado.loc[~es_continence], representantes_table)
    return pd.concat([continence, resto], ignore_index=True)


def procesar_ciclo(
    productos: pd.DataFrame | None,
    servicios: pd.DataFrame | None,
    envios_nacionales: pd.DataFrame | None,
    producto_table: pd.DataFrame,
    representantes_table: pd.DataFrame,
    convenios_table: pd.DataFrame,
    mes: int,
) -> pd.DataFrame:
    """Full Epic 1 pipeline: homologacion -> asignacion (Reglas 1/2/3 + Repartir
    + directrices) -> excepciones. One row in, at least one row out (splits
    only ever add rows, FR-9's testable guarantee)."""
    parts = []
    if productos is not None and not productos.empty:
        part = _procesar_productos_o_servicios(productos, producto_table, representantes_table, convenios_table)
        part["Origen"] = "producto"
        parts.append(part)
    if servicios is not None and not servicios.empty:
        part = _procesar_productos_o_servicios(servicios, producto_table, representantes_table, convenios_table)
        part["Origen"] = "servicio"
        parts.append(part)
    if envios_nacionales is not None and not envios_nacionales.empty:
        part = asignar_regla3_envios_nacionales(envios_nacionales)
        part["Origen"] = "envio_nacional"
        parts.append(part)

    if not parts:
        raise ValueError("No hay ningún insumo de ventas cargado para procesar.")

    combinado = pd.concat(parts, ignore_index=True)
    combinado = aplicar_directrices(combinado, mes)
    combinado = split_repartir(combinado)
    return marcar_excepciones(combinado)


def calcular_comision_ilustrativa(df: pd.DataFrame, valor_referencia: float, sede_col: str = "Sede") -> pd.DataFrame:
    """FR-12: NOT an official commission. `valor_referencia` is split, per
    Sede, across the distinct representatives Fase 1 already assigned there
    -- counted by Grupo_Vendedor (the actual assignment key, PRD S3 Glosario)
    rather than Representante name, so the same person spelled two ways in
    the source data (found in code review: "Adriana M. Rojas" vs "Adriana
    Marcela Rojas") is never counted twice."""
    out = df.copy()
    if sede_col not in out.columns:
        departamento = _series_or_nan(out, "Departamento")
        convenio = _series_or_nan(out, "Convenio")
        out[sede_col] = departamento.where(departamento.notna(), convenio)

    asignados = out.dropna(subset=["Grupo_Vendedor"])
    reps_por_sede = asignados.groupby(sede_col, dropna=False)["Grupo_Vendedor"].nunique()

    def _comision(row):
        if pd.isna(row["Grupo_Vendedor"]):
            return None
        sede = row[sede_col]
        n = reps_por_sede.get(sede)
        if not n:
            return None
        return round(valor_referencia / n, 2)

    out["Comision_Ilustrativa"] = out.apply(_comision, axis=1)
    return out
