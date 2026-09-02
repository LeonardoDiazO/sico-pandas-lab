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

    categoricas = [c["name"] for c in learner_profile["columns"] if c["type"] == TYPE_CATEGORICA]
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
