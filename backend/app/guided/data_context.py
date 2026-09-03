"""Resolves a learner's own uploaded-Excel column profile into the concrete
{table_var, roles} substitution a guided lesson's example code and challenge
checker need, so a lesson that "pretends" to use real data actually does when
the learner has some loaded -- instead of always falling back to a fixed
synthetic sico table (df_02_movimiento/mov_item/mov_cantidad/mov_neto).

Deliberately scoped to the lessons/challenges where a single flat table is
enough to demonstrate the concept (01-fundamentos, 03-agrupar, 05-graficas).
02-filtrar-ordenar narrates a specific business scenario (negative quantities
= devoluciones) that would stop being true for arbitrary data, and
04-combinar-tablas teaches a JOIN, which inherently needs two related tables
a single uploaded Excel can't provide -- both stay on their static synthetic
example on purpose, not by oversight.
"""
import re

from app.data_access.excel_profiler import TYPE_CATEGORICA, TYPE_NUMERICA

# Per lesson: the synthetic identifiers its own static content.py steps use,
# and the semantic role each one plays. resolve_context() maps each role to
# a real column from the learner's profile, in the same relative order they
# already appear together in that lesson's own synthetic table -- not by
# guessing which of the user's columns is "quantity-like" vs "money-like".
LESSON_ROLES = {
    "01-fundamentos": {"table_var_default": "df_02_movimiento", "cat": "mov_item", "num1": "mov_cantidad", "num2": "mov_neto"},
    "03-agrupar": {"table_var_default": "df_02_movimiento", "cat": "mov_item", "num1": "mov_cantidad", "num2": "mov_neto"},
    "05-graficas": {"table_var_default": "df_02_movimiento", "cat": "mov_item", "num1": "mov_cantidad"},
}


def _is_degenerate_categorical(column):
    """A categorical column whose ONLY value across every non-null row is
    the same one - e.g. a "Devolución" (return) column that reads "0" on
    every row of a sales report where returns never happened - has nothing
    to group by: every row lands in the same bucket. Its uniqueRatio is at
    (or near) the theoretical minimum, which would otherwise make it win
    the low-cardinality sort above ahead of any genuinely useful dimension
    (real bug found in production, right next to the provider-code one
    above: a handful of always-"0" columns outranked "Vdor"). sampleValues
    is capped at 5 distinct values by excel_profiler._column_stats, so
    fewer than 2 of them unambiguously means "exactly one distinct value
    total", never "we just didn't sample more". Profiles that predate
    sampleValues (missing the key) can't be checked this way, so they're
    never treated as degenerate - same fail-open stance as the missing
    uniqueRatio case above.
    """
    sample_values = column.get("sampleValues")
    return sample_values is not None and len(sample_values) < 2


def resolve_context(lesson_id, learner_profile):
    """Returns {"table_var": str, "roles": {role: real_column_name, ...}} if
    this lesson is in scope AND the learner's profile has enough columns to
    fill every role the lesson needs, or None otherwise -- callers must treat
    None as "serve the static content exactly as it is today", never as a
    partial substitution (a code snippet mixing real and synthetic names
    would be more confusing than either alone).
    """
    roles_needed = LESSON_ROLES.get(lesson_id)
    if roles_needed is None or learner_profile is None:
        return None

    # Sorted by uniqueRatio ascending, not file order - a categorical column
    # with hundreds of distinct values (e.g. a provider code) makes a
    # confusing first "group by this" example next to one with a handful
    # (e.g. a salesperson code): the printed table/insight sentence for the
    # former reads as noise ("47 de 210 categorías concentran...") where the
    # latter reads as an actual takeaway ("2 de 6..."). Real bug found in
    # production: the file-order-first pick landed on a ~200-value provider
    # code instead of the 6-value salesperson column sitting right next to
    # it in the same file. Missing/older profiles without uniqueRatio sort
    # last (worst case), never crash. Degenerate (single-value) columns are
    # excluded entirely - see _is_degenerate_categorical - otherwise this
    # same ascending sort would prefer them over any real dimension, since
    # "always the same value" has the lowest possible uniqueRatio of all.
    categoricas = [
        c["name"]
        for c in sorted(learner_profile["columns"], key=lambda c: c.get("uniqueRatio", 1.0))
        if c["type"] == TYPE_CATEGORICA and not _is_degenerate_categorical(c)
    ]
    numericas = [c["name"] for c in learner_profile["columns"] if c["type"] == TYPE_NUMERICA]

    resolved = {}
    if "cat" in roles_needed:
        if not categoricas:
            return None
        resolved["cat"] = categoricas[0]

    needs_num1 = "num1" in roles_needed
    needs_num2 = "num2" in roles_needed
    if needs_num1 and needs_num2:
        # Both roles land in the SAME synthetic dict literal (see
        # 01-fundamentos step 1.2 / 03-agrupar step 3.1's
        # pd.DataFrame({'mov_cantidad': ..., 'mov_neto': ...})). Reusing one
        # real column for both would substitute two DIFFERENT dict keys
        # with the SAME name -- valid Python, but it silently drops the
        # first value and keeps only the second, which reads as a mistake,
        # not an example. Require two genuinely distinct numeric columns;
        # otherwise fall back to the fully static example rather than show
        # a technically-valid but misleading one.
        if len(numericas) < 2:
            return None
        resolved["num1"], resolved["num2"] = numericas[0], numericas[1]
    elif needs_num1:
        if not numericas:
            return None
        resolved["num1"] = numericas[0]
    elif needs_num2:
        if not numericas:
            return None
        resolved["num2"] = numericas[0]

    return {"table_var": learner_profile["variable"], "roles": resolved}


def substitute_identifiers(text, lesson_id, context):
    """Replaces every synthetic identifier this lesson's static content uses
    (its table variable name and each role's synthetic column name) with the
    real name `context` resolved, as whole identifiers only (so e.g.
    substituting `mov_item` never touches `mov_item_id` or similar). Applied
    to both `code` and prose (`explanation`/`prompt`) so the two never end up
    referencing different names."""
    roles_needed = LESSON_ROLES[lesson_id]
    mapping = {roles_needed["table_var_default"]: context["table_var"]}
    for role, synthetic_name in roles_needed.items():
        if role == "table_var_default":
            continue
        mapping[synthetic_name] = context["roles"][role]

    for old, new in mapping.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text
