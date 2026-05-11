"""Reference data for the procurement agent.

`seed()` and `main()` populate departments, vendors, and policies — the
lookup data the agent needs to evaluate any request. Purchase requests
themselves are seeded out-of-band through the API: see `scripts/` at the
repo root for the bulk helper that POSTs the demo set against a running
agent.
"""

import sqlite3
from pathlib import Path

from src.database import (
    get_connection,
    init_schema,
    insert_department,
    insert_policy,
    insert_vendor,
)
from src.models import Department, Policy, Vendor, VendorStatus


def departments() -> list[Department]:
    return [
        Department(name="Engineering", headcount=50, quarterly_budget=200_000),
        Department(name="Marketing", headcount=25, quarterly_budget=150_000),
        Department(name="Customer Success", headcount=15, quarterly_budget=75_000),
        Department(name="Sales", headcount=30, quarterly_budget=125_000),
        Department(name="Security", headcount=10, quarterly_budget=100_000),
    ]


def vendors() -> list[Vendor]:
    return [
        Vendor(name="TechFlow", status=VendorStatus.PREFERRED, categories=["software"], notes="Broad catalog, preferred vendor"),
        Vendor(name="Vertex Solutions", status=VendorStatus.APPROVED, categories=["infrastructure"], notes="Good relationship, emergency pricing during March outage"),
        Vendor(name="CloudBase Inc", status=VendorStatus.APPROVED, categories=["cloud services"], notes="SLA issues noted"),
        Vendor(name="DataStream Analytics", status=VendorStatus.APPROVED, categories=["analytics"], notes="Cost overrun history"),
        Vendor(name="Insight Partners", status=VendorStatus.SUSPENDED, categories=["consulting"], notes="Double-billed in 2024, billing dispute"),
        Vendor(name="SecureNet Pro", status=VendorStatus.APPROVED, categories=["security tools"]),
        Vendor(name="CreativeHub", status=VendorStatus.APPROVED, categories=["marketing", "design tools"]),
        Vendor(name="OmniConsult", status=VendorStatus.APPROVED, categories=["consulting"]),
        Vendor(name="FreshStack", status=VendorStatus.NOT_LISTED, categories=["support tools", "engineering tools"], notes="New vendor, not on approved list"),
    ]


def policies() -> list[Policy]:
    return [
        Policy(
            name="Software Procurement",
            description="Approval thresholds for software purchases",
            rules=[
                "Up to $5,000: auto-approved",
                "$5,000-$25,000: requires manager approval",
                "Over $25,000: requires VP approval",
            ],
        ),
        Policy(
            name="Hardware Procurement",
            description="Approval thresholds for hardware purchases",
            rules=[
                "Up to $2,000: auto-approved",
                "Over $2,000: requires manager approval",
            ],
        ),
        Policy(
            name="Consulting Engagements",
            description="Approval rules for consulting services",
            rules=[
                "All consulting engagements require manager approval",
                "Over $50,000: requires VP approval",
            ],
        ),
        Policy(
            name="Vendor Consolidation Directive",
            description="Q2 directive to consolidate to single vendors per category",
            rules=[
                "Prefer existing preferred/approved vendors",
                "New vendors require strong business justification",
            ],
        ),
        Policy(
            name="Emergency Purchases",
            description="Rules for emergency procurement",
            rules=[
                "Can bypass normal approval flow",
                "Requires post-hoc review within 48 hours",
            ],
        ),
    ]


def seed(conn: sqlite3.Connection) -> None:
    """Populate reference data (departments, vendors, policies). Commits when done.

    Purchase requests are NOT inserted here — they go through the API so
    each one gets a real agent assessment. Use the helper at
    `scripts/seed_requests.py` to populate sample requests against a
    running server.
    """
    init_schema(conn)

    for dept in departments():
        insert_department(conn, dept)

    for vendor in vendors():
        insert_vendor(conn, vendor)

    for policy in policies():
        insert_policy(conn, policy)

    conn.commit()


def main(db_path: Path | None = None) -> None:
    """Seed reference data into the active variant's DB (or baseline if EXPERIMENT_VARIANT unset).

    Pass `db_path` explicitly to override the env-var-derived path (useful for tests).
    """
    from src.database import resolve_db_path

    path = db_path or resolve_db_path()
    # Remove existing DB so we start fresh
    if path.exists():
        path.unlink()

    conn = get_connection(path)
    try:
        seed(conn)
        print(f"Seeded reference data at {path}")
        print(f"  {len(departments())} departments")
        print(f"  {len(vendors())} vendors")
        print(f"  {len(policies())} policies")
        print()
        print("Database starts empty of purchase requests.")
        print("To populate sample requests against a running API:")
        print("  cd scripts/ && uv run python seed_requests.py")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
