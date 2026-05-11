"""Synthetic purchase-request data for the demo.

Two sets:

- `curated_requests()` — 30 hand-written requests (PR-001..PR-030) telling
  a deliberate demo narrative. Specific vendors and amounts are chosen to
  exercise the agent's policy / vendor / budget paths and to set up Vera
  Fye's institutional knowledge in `reviewer-agent`.
- `generated_requests()` — 100 procedurally-generated requests
  (PR-031..PR-130) with a fixed RNG seed so the output is reproducible.
  The mix is engineered to give every recommendation branch coverage:
  ~40 auto-approve, ~30 rejection (suspended or not-on-list vendors),
  ~30 mid-/VP-tier candidates that should land on flag-for-review.

Returns plain `dict` payloads ready to JSON-serialize. Module is
deliberately decoupled from `procurement-agent` — there's no Pydantic
import here; the agent owns the wire schema and validates on receipt.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

PurchaseRequestDict = dict[str, Any]


def curated_requests() -> list[PurchaseRequestDict]:
    """30 hand-curated requests telling the demo narrative."""
    return [
        # ── Batch 1: Establishing Patterns (1-10) ──
        {
            "id": "PR-001",
            "requester": "Alex Rivera",
            "department": "Engineering",
            "item": "TechFlow IDE licenses (10 seats)",
            "vendor": "TechFlow",
            "amount": 3200,
            "justification": "Team needs upgraded IDE for new microservices project",
            "urgency": "routine",
        },
        {
            "id": "PR-002",
            "requester": "Priya Sharma",
            "department": "Marketing",
            "item": "CreativeHub annual renewal",
            "vendor": "CreativeHub",
            "amount": 12000,
            "justification": "Annual renewal for design platform used by creative team",
            "urgency": "routine",
        },
        {
            "id": "PR-003",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "CloudBase Inc expanded storage",
            "vendor": "CloudBase Inc",
            "amount": 8500,
            "justification": "Current storage at 90% capacity, need expansion for Q3 pipeline data",
            "urgency": "urgent",
        },
        {
            "id": "PR-004",
            "requester": "Jamie Kowalski",
            "department": "Engineering",
            "item": "DataStream Analytics add-on module",
            "vendor": "DataStream Analytics",
            "amount": 6800,
            "justification": "Need analytics add-on for observability pipeline integration",
            "urgency": "routine",
        },
        {
            "id": "PR-005",
            "requester": "Sofia Martinez",
            "department": "Customer Success",
            "item": "FreshStack support tool",
            "vendor": "FreshStack",
            "amount": 4200,
            "justification": "Critical gap in support tooling, team is understaffed and handling tickets manually",
            "urgency": "urgent",
        },
        {
            "id": "PR-006",
            "requester": "Tyler Brooks",
            "department": "Marketing",
            "item": "OmniConsult brand strategy engagement",
            "vendor": "OmniConsult",
            "amount": 45000,
            "justification": "Need comprehensive brand refresh strategy for H2 campaigns",
            "urgency": "routine",
        },
        {
            "id": "PR-007",
            "requester": "Chen Wei",
            "department": "Security",
            "item": "SecureNet Pro vulnerability scanner upgrade",
            "vendor": "SecureNet Pro",
            "amount": 22000,
            "justification": "Current scanner version EOL next month, upgrade includes new CVE detection",
            "urgency": "urgent",
        },
        {
            "id": "PR-008",
            "requester": "Jamie Kowalski",
            "department": "Engineering",
            "item": "Insight Partners architecture review",
            "vendor": "Insight Partners",
            "amount": 35000,
            "justification": "Need external architecture review before platform migration",
            "urgency": "routine",
        },
        {
            "id": "PR-009",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "TechFlow CRM add-on",
            "vendor": "TechFlow",
            "amount": 15000,
            "justification": "CRM add-on for pipeline analytics and forecasting",
            "urgency": "routine",
        },
        {
            "id": "PR-010",
            "requester": "Alex Rivera",
            "department": "Engineering",
            "item": "CloudBase Inc dev environments",
            "vendor": "CloudBase Inc",
            "amount": 19000,
            "justification": "Need cloud dev environments for new hires and contractor onboarding",
            "urgency": "routine",
        },
        # ── Batch 2: Building Precedent (11-20) ──
        {
            "id": "PR-011",
            "requester": "Sofia Martinez",
            "department": "Customer Success",
            "item": "FreshStack additional licenses",
            "vendor": "FreshStack",
            "amount": 2800,
            "justification": "Team adopted FreshStack from PR-005, need 5 more seats",
            "urgency": "routine",
        },
        {
            "id": "PR-012",
            "requester": "Priya Sharma",
            "department": "Marketing",
            "item": "CreativeHub premium tier upgrade",
            "vendor": "CreativeHub",
            "amount": 28000,
            "justification": "Need premium features for upcoming product launch campaign, urgent timeline",
            "urgency": "urgent",
        },
        {
            "id": "PR-013",
            "requester": "Jamie Kowalski",
            "department": "Engineering",
            "item": "DataStream Analytics enterprise license",
            "vendor": "DataStream Analytics",
            "amount": 18500,
            "justification": "Need analytics platform for new observability pipeline",
            "urgency": "routine",
        },
        {
            "id": "PR-014",
            "requester": "Chen Wei",
            "department": "Security",
            "item": "Emergency firewall hardware",
            "vendor": "SecureNet Pro",
            "amount": 8000,
            "justification": "Firewall failure detected, need immediate replacement to maintain perimeter security",
            "urgency": "emergency",
        },
        {
            "id": "PR-015",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "LeadGenPro outbound tool",
            "vendor": "LeadGenPro",
            "amount": 9500,
            "justification": "New outbound prospecting tool to improve SDR efficiency",
            "urgency": "routine",
        },
        {
            "id": "PR-016",
            "requester": "Sofia Martinez",
            "department": "Customer Success",
            "item": "Vertex Solutions integration support",
            "vendor": "Vertex Solutions",
            "amount": 12000,
            "justification": "Need integration support for CRM-to-support pipeline, customer escalations increasing",
            "urgency": "urgent",
        },
        {
            "id": "PR-017",
            "requester": "Tyler Brooks",
            "department": "Marketing",
            "item": "OmniConsult social media audit",
            "vendor": "OmniConsult",
            "amount": 15000,
            "justification": "Social media presence needs professional audit before H2 push",
            "urgency": "routine",
        },
        {
            "id": "PR-018",
            "requester": "Alex Rivera",
            "department": "Engineering",
            "item": "Vertex Solutions additional compute capacity",
            "vendor": "Vertex Solutions",
            "amount": 32000,
            "justification": "Production scaling needs for Q3 launch, current capacity insufficient for load tests",
            "urgency": "urgent",
        },
        {
            "id": "PR-019",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "DataStream Analytics reporting module",
            "vendor": "DataStream Analytics",
            "amount": 7200,
            "justification": "Need reporting module for quarterly sales analytics dashboards",
            "urgency": "routine",
        },
        {
            "id": "PR-020",
            "requester": "Chen Wei",
            "department": "Security",
            "item": "OmniConsult penetration testing",
            "vendor": "OmniConsult",
            "amount": 55000,
            "justification": "Annual penetration test required by compliance, scope increased due to new services",
            "urgency": "routine",
        },
        # ── Batch 3: Testing the Compounding Loop (21-30) ──
        {
            "id": "PR-021",
            "requester": "Sofia Martinez",
            "department": "Customer Success",
            "item": "FreshStack enterprise plan",
            "vendor": "FreshStack",
            "amount": 11000,
            "justification": "Upgrading to enterprise plan, FreshStack is now core to CS workflow",
            "urgency": "routine",
        },
        {
            "id": "PR-022",
            "requester": "Jamie Kowalski",
            "department": "Engineering",
            "item": "CloudBase Inc additional services",
            "vendor": "CloudBase Inc",
            "amount": 14000,
            "justification": "Need additional cloud services for staging environment expansion",
            "urgency": "routine",
        },
        {
            "id": "PR-023",
            "requester": "Tyler Brooks",
            "department": "Marketing",
            "item": "BrandForce consulting engagement",
            "vendor": "BrandForce",
            "amount": 20000,
            "justification": "Urgent brand positioning work needed before competitor launch",
            "urgency": "urgent",
        },
        {
            "id": "PR-024",
            "requester": "Alex Rivera",
            "department": "Engineering",
            "item": "DataStream Analytics training package",
            "vendor": "DataStream Analytics",
            "amount": 4500,
            "justification": "Team training on DataStream platform for new engineers",
            "urgency": "routine",
        },
        {
            "id": "PR-025",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "Vertex Solutions premium support",
            "vendor": "Vertex Solutions",
            "amount": 16000,
            "justification": "Premium support tier for faster response on infrastructure issues",
            "urgency": "routine",
        },
        {
            "id": "PR-026",
            "requester": "Sofia Martinez",
            "department": "Customer Success",
            "item": "Vertex Solutions emergency incident response",
            "vendor": "Vertex Solutions",
            "amount": 25000,
            "justification": "Critical customer-facing incident, need immediate Vertex support engagement",
            "urgency": "emergency",
        },
        {
            "id": "PR-027",
            "requester": "Priya Sharma",
            "department": "Marketing",
            "item": "CreativeHub seat reduction and plan change",
            "vendor": "CreativeHub",
            "amount": -3000,
            "justification": "Reducing from 20 to 12 seats based on actual usage audit",
            "urgency": "routine",
        },
        {
            "id": "PR-028",
            "requester": "Jamie Kowalski",
            "department": "Engineering",
            "item": "FreshStack engineering tools",
            "vendor": "FreshStack",
            "amount": 8000,
            "justification": "FreshStack engineering tooling for developer productivity improvements",
            "urgency": "routine",
        },
        {
            "id": "PR-029",
            "requester": "Chen Wei",
            "department": "Security",
            "item": "Vertex Solutions security monitoring",
            "vendor": "Vertex Solutions",
            "amount": 45000,
            "justification": "24/7 security monitoring service, critical for SOC2 compliance",
            "urgency": "urgent",
        },
        {
            "id": "PR-030",
            "requester": "Marcus Johnson",
            "department": "Sales",
            "item": "Insight Partners sales training",
            "vendor": "Insight Partners",
            "amount": 28000,
            "justification": "Sales team training program for new enterprise selling methodology",
            "urgency": "routine",
        },
    ]


def generated_requests() -> list[PurchaseRequestDict]:
    """100 procedurally-generated requests (PR-031..PR-130).

    Output is deterministic — fixed RNG seed (42). Distribution:
      - 40 auto-approve candidates (small amount + approved/preferred vendor)
      - 30 rejection candidates (Insight Partners or invented not-on-list vendor)
      - 30 mid-/VP-tier candidates (>= $5,500 + approved vendor)
    """
    rng = random.Random(42)

    requesters = [
        "Alex Rivera", "Priya Sharma", "Marcus Johnson", "Jamie Kowalski",
        "Sofia Martinez", "Tyler Brooks", "Chen Wei", "Maya Patel",
        "Daniel Cho", "Riley Thomas", "Emma Lindgren",
    ]
    departments_pool = ["Engineering", "Marketing", "Customer Success", "Sales", "Security"]
    approved_vendors = [
        "TechFlow", "Vertex Solutions", "CloudBase Inc", "DataStream Analytics",
        "SecureNet Pro", "CreativeHub", "OmniConsult",
    ]
    not_listed_vendors = [
        "QuickShip Pro", "Veridian Cloud", "PulseDB", "RoamWorks",
        "MomentumCRM", "Stratos Analytics", "FuseHQ", "Apex Tooling",
        "Nimbus Stack", "Cortex Labs",
    ]

    auto_items: list[tuple[str, str]] = [
        ("{vendor} — single-seat license", "Adding one user to existing team plan"),
        ("{vendor} annual renewal (1 user)", "Annual auto-renewal for current user"),
        ("{vendor} training credit pack", "Self-paced training credits for one engineer"),
        ("{vendor} small add-on module", "Small add-on for current setup, single team"),
        ("{vendor} docs portal access", "External docs portal for one team"),
        ("{vendor} plugin license", "Plugin for existing platform, one workspace"),
        ("{vendor} monthly tier (3 seats)", "Three-seat monthly subscription for sub-team"),
        ("{vendor} usage top-up", "Additional API credits for the rest of the quarter"),
    ]
    mid_items: list[tuple[str, str]] = [
        ("{vendor} expansion (10 seats)", "Adding 10 seats as the team grows"),
        ("{vendor} enterprise renewal", "Annual renewal of existing enterprise plan"),
        ("{vendor} integration engineering", "Custom integration with internal stack"),
        ("{vendor} premium support upgrade", "Upgrade to premium tier for faster response"),
        ("{vendor} workshop facilitation", "Two-day workshop facilitated for the team"),
        ("{vendor} audit and assessment", "Independent audit and assessment engagement"),
        ("{vendor} capacity expansion", "Doubling capacity ahead of Q3 launch"),
        ("{vendor} platform migration", "Migration assistance for upcoming platform change"),
    ]
    rejection_items: list[tuple[str, str]] = [
        ("Trial of {vendor}", "Small trial of unfamiliar vendor"),
        ("New tooling — {vendor}", "Evaluating a new product not yet on the approved list"),
        ("Consulting block — {vendor}", "External consulting services"),
        ("{vendor} licensing", "Standard licensing arrangement"),
        ("{vendor} pilot project", "Pilot project to evaluate fit"),
    ]
    urgencies = ["routine", "routine", "routine", "urgent", "emergency"]

    results: list[PurchaseRequestDict] = []
    pid = 31

    def _make(vendor: str, item_t: str, just_t: str, amount: float) -> PurchaseRequestDict:
        nonlocal pid
        record = {
            "id": f"PR-{pid:03d}",
            "requester": rng.choice(requesters),
            "department": rng.choice(departments_pool),
            "item": item_t.format(vendor=vendor),
            "vendor": vendor,
            "amount": round(amount, 2),
            "justification": just_t,
            "urgency": rng.choice(urgencies),
        }
        pid += 1
        return record

    # 40 auto-approve
    for _ in range(40):
        vendor = rng.choice(approved_vendors)
        item_t, just_t = rng.choice(auto_items)
        results.append(_make(vendor, item_t, just_t, rng.uniform(150, 4800)))

    # 30 rejection
    for _ in range(30):
        if rng.random() < 0.5:
            vendor = "Insight Partners"
        else:
            vendor = rng.choice(not_listed_vendors)
        item_t, just_t = rng.choice(rejection_items)
        results.append(_make(vendor, item_t, just_t, rng.uniform(500, 30000)))

    # 30 mid-/VP-tier
    for _ in range(30):
        vendor = rng.choice(approved_vendors)
        item_t, just_t = rng.choice(mid_items)
        results.append(_make(vendor, item_t, just_t, rng.uniform(5500, 50000)))

    return results


def all_requests() -> list[PurchaseRequestDict]:
    """Curated 30 + generated 100 — what the seed script POSTs."""
    return curated_requests() + generated_requests()


def to_create_body(record: PurchaseRequestDict) -> PurchaseRequestDict:
    """Strip server-assigned fields (`id`, `status`, timestamps) for POST.

    The server assigns its own monotonic `PR-NNN` id and timestamps; we
    only send the user-supplied fields the API expects on
    `PurchaseRequestCreate`.
    """
    return {
        "requester": record["requester"],
        "department": record["department"],
        "item": record["item"],
        "vendor": record["vendor"],
        "amount": record["amount"],
        "justification": record["justification"],
        "urgency": record["urgency"],
    }


def assign_curated_timestamps(reqs: list[PurchaseRequestDict]) -> list[PurchaseRequestDict]:
    """Attach `created_at`/`updated_at` to the curated 30 in three batches.

    Useful for direct DB inserts (e.g. tests that bypass the API). Not
    used by the seed script — the API assigns timestamps server-side.
    """
    now = datetime.now(UTC).replace(second=0, microsecond=0, tzinfo=None)
    batch_starts = [
        now - timedelta(days=5),
        now - timedelta(days=3),
        now - timedelta(days=1),
    ]
    batches = [reqs[:10], reqs[10:20], reqs[20:]]
    result: list[PurchaseRequestDict] = []
    for batch, start in zip(batches, batch_starts):
        for i, req in enumerate(batch):
            offset = timedelta(hours=2 * i + (i % 3), minutes=15 * (i % 4))
            created = start + offset
            result.append({**req, "created_at": created.isoformat(), "updated_at": created.isoformat()})
    return result


def assign_generated_timestamps(reqs: list[PurchaseRequestDict]) -> list[PurchaseRequestDict]:
    """Spread generated requests over the last 30 days (deterministic seed)."""
    rng = random.Random(43)
    now = datetime.now(UTC).replace(second=0, microsecond=0, tzinfo=None)
    result: list[PurchaseRequestDict] = []
    for req in reqs:
        days_ago = rng.uniform(0.25, 30)
        created = (now - timedelta(days=days_ago)).replace(second=0, microsecond=0)
        result.append({**req, "created_at": created.isoformat(), "updated_at": created.isoformat()})
    return result
