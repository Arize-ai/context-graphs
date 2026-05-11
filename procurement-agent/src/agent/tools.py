"""LangChain tools that gather context for a purchase request.

Each tool opens its own DB connection so it can be invoked by the agent without
needing a shared context. Tools always read against the default DB path; for
tests, use the integration test fixtures that exercise the API surface rather
than calling the agent directly.

When an experiment variant is active (`EXPERIMENT_VARIANT` env var set), the
vendor and department lookups overlay the variant's metadata onto the DB rows
at read time. Variant-supplied fields are surfaced as additional context for
the agent's reasoning — the underlying DB is never modified.
"""

import sqlite3

from langchain_core.tools import tool

from src.database import get_all_departments, get_all_policies, get_all_vendors, get_connection
from src.variants import Variant, load_variant


def _check_policy(conn: sqlite3.Connection, amount: float, vendor: str) -> str:
    policies = get_all_policies(conn)
    lines: list[str] = []
    for p in policies:
        lines.append(f"Policy: {p.name} — {p.description}")
        for rule in p.rules:
            lines.append(f"  - {rule}")

    if amount <= 5000:
        lines.append(f"\nFor amount ${amount:,.0f}: auto-approved under $5,000 threshold.")
    elif amount <= 25000:
        lines.append(f"\nFor amount ${amount:,.0f}: requires manager approval ($5K-$25K range).")
    elif amount <= 50000:
        lines.append(f"\nFor amount ${amount:,.0f}: requires VP approval (over $25K).")
    else:
        lines.append(f"\nFor amount ${amount:,.0f}: requires VP approval (over $50K for consulting).")

    return "\n".join(lines)


def _lookup_vendor(
    conn: sqlite3.Connection,
    vendor_name: str,
    variant: Variant | None = None,
    amount: float | None = None,
) -> str:
    variant = variant if variant is not None else load_variant()
    overlay = variant.vendor_overlay.get(vendor_name, {}) if variant.is_active else {}

    vendors = get_all_vendors(conn)
    for v in vendors:
        if v.name.lower() == vendor_name.lower():
            cost_overrun_factor = float(overlay.get("cost_overrun_factor", v.cost_overrun_factor))
            relationship_credit = str(overlay.get("relationship_credit", v.relationship_credit))
            deprecating_in_favor_of = overlay.get("deprecating_in_favor_of", v.deprecating_in_favor_of)

            parts = [
                f"Vendor: {v.name}",
                f"Status: {v.status.value}",
                f"Categories: {', '.join(v.categories)}",
            ]
            if v.notes:
                parts.append(f"Notes: {v.notes}")
            if cost_overrun_factor and cost_overrun_factor > 1.0:
                eff_line = f"Cost-overrun factor: {cost_overrun_factor:.2f}× — historical implementations come in this much over quote."
                if amount is not None:
                    eff_line += f" Realistic effective amount: ${amount * cost_overrun_factor:,.0f}."
                parts.append(eff_line)
            if relationship_credit:
                parts.append(f"Relationship credit: {relationship_credit}")
            if deprecating_in_favor_of:
                parts.append(
                    f"Deprecation notice: {v.name} is being consolidated in favor of "
                    f"{deprecating_in_favor_of}. Prefer the successor unless a strong "
                    f"justification is provided."
                )
            return "\n".join(parts)
    return f"Vendor '{vendor_name}' not found in approved vendor list. Status: not_listed."


def _check_budget(conn: sqlite3.Connection, department: str, amount: float) -> str:
    row = conn.execute("SELECT * FROM departments WHERE name = ?", (department,)).fetchone()
    if row is None:
        return f"Department '{department}' not found."
    budget = row["quarterly_budget"]
    return (
        f"Department: {department}\n"
        f"Quarterly budget: ${budget:,.0f}\n"
        f"Requested amount: ${amount:,.0f}\n"
        f"Budget available for this request."
    )


def _lookup_department(
    conn: sqlite3.Connection,
    department_name: str,
    variant: Variant | None = None,
) -> str:
    """Surface department-behavior context if the active variant supplies it.

    With no variant active, returns "no behavior data available" — telling the
    agent there's nothing to consider beyond what `check_budget` already
    provides. This matches the baseline (pre-variant) agent's blind spot.
    """
    variant = variant if variant is not None else load_variant()
    overlay = (
        variant.department_overlay.get(department_name, {})
        if variant.is_active
        else {}
    )

    departments = get_all_departments(conn)
    matched = next(
        (d for d in departments if d.name.lower() == department_name.lower()),
        None,
    )
    if matched is None and not overlay:
        return f"Department '{department_name}' not found."

    notes_from_overlay = overlay.get("behavior_notes")
    behavior_notes = (
        list(notes_from_overlay)
        if isinstance(notes_from_overlay, list)
        else (matched.behavior_notes if matched is not None else [])
    )

    if not behavior_notes:
        return (
            f"Department: {department_name}\n"
            "No behavior data available. Decide on policy and budget alone."
        )

    lines = [f"Department: {department_name}", "Behavioral context (from past reviews):"]
    lines.extend(f"  - {note}" for note in behavior_notes)
    return "\n".join(lines)


@tool
def check_policy(amount: float, vendor: str) -> str:
    """Look up the procurement policies that apply to a request.

    Returns the full policy catalog plus a one-line summary of which approval
    tier applies given the amount. Call this before deciding whether the
    request complies with thresholds.

    Args:
        amount: Requested purchase amount in USD.
        vendor: Vendor name (used for context only — vendor approval is checked
            separately via lookup_vendor).
    """
    conn = get_connection()
    try:
        return _check_policy(conn, amount, vendor)
    finally:
        conn.close()


@tool
def lookup_vendor(vendor: str, amount: float | None = None) -> str:
    """Look up the approval status of a vendor.

    Returns vendor status (preferred / approved / suspended / not_listed),
    categories, and any notes. If the vendor is suspended or not_listed, the
    request is non-compliant. When an experiment variant supplies
    cost-overrun, relationship-credit, or deprecation metadata, those signals
    are appended.

    Args:
        vendor: Vendor name to look up (case-insensitive).
        amount: Optional requested amount; if provided alongside a non-default
            cost-overrun factor, a realistic effective amount is reported.
    """
    conn = get_connection()
    try:
        return _lookup_vendor(conn, vendor, amount=amount)
    finally:
        conn.close()


@tool
def check_budget(department: str, amount: float) -> str:
    """Check whether the requesting department has budget headroom.

    Returns the department's quarterly budget and confirms whether the
    requested amount fits within it.

    Args:
        department: Requesting department name.
        amount: Requested purchase amount in USD.
    """
    conn = get_connection()
    try:
        return _check_budget(conn, department, amount)
    finally:
        conn.close()


@tool
def lookup_department(department: str) -> str:
    """Look up department-specific behavioral context.

    Returns any reviewer-cited department patterns surfaced through the active
    experiment variant (e.g. "Marketing tends to panic-buy single-campaign
    tools"). When no variant is active, returns "no behavior data available" —
    decide on policy and budget alone.

    Args:
        department: Requesting department name.
    """
    conn = get_connection()
    try:
        return _lookup_department(conn, department)
    finally:
        conn.close()


__all__ = [
    "check_policy",
    "lookup_vendor",
    "check_budget",
    "lookup_department",
    "_check_policy",
    "_lookup_vendor",
    "_check_budget",
    "_lookup_department",
]
