"""Inline test fixtures for integration tests.

Independent of `scripts/synthetic_data.py` — that's the demo data, owned
by the seed script. Tests own their own small set so:

- they don't reach across the repo,
- they validate agent behavior, not demo content,
- adjusting the demo data doesn't break tests.

The set is sized to keep existing assertions stable (`SEEDED_REQUEST_COUNT`,
`PR-005 vendor = FreshStack`) without bloating the suite.
"""

from datetime import datetime, timedelta

from src.models import PurchaseRequest, RequestStatus, Urgency

_BASE_TS = datetime(2026, 4, 1, 10, 0, 0)


def _build() -> list[PurchaseRequest]:
    fields: list[tuple[str, str, str, str, float, str, Urgency]] = [
        ("Alex Rivera", "Engineering", "TechFlow IDE licenses", "TechFlow", 3200, "Team needs upgraded IDE", Urgency.ROUTINE),
        ("Priya Sharma", "Marketing", "CreativeHub annual renewal", "CreativeHub", 12000, "Annual renewal", Urgency.ROUTINE),
        ("Marcus Johnson", "Sales", "CloudBase storage expansion", "CloudBase Inc", 8500, "Storage at 90% capacity", Urgency.URGENT),
        ("Jamie Kowalski", "Engineering", "DataStream add-on", "DataStream Analytics", 6800, "Observability pipeline", Urgency.ROUTINE),
        # PR-005 — FreshStack (referenced explicitly by tests)
        ("Sofia Martinez", "Customer Success", "FreshStack support tool", "FreshStack", 4200, "Support tooling gap", Urgency.URGENT),
        ("Tyler Brooks", "Marketing", "OmniConsult brand strategy", "OmniConsult", 45000, "Brand refresh", Urgency.ROUTINE),
        ("Chen Wei", "Security", "SecureNet upgrade", "SecureNet Pro", 22000, "Scanner EOL", Urgency.URGENT),
        ("Jamie Kowalski", "Engineering", "Insight Partners architecture review", "Insight Partners", 35000, "Pre-migration review", Urgency.ROUTINE),
        ("Marcus Johnson", "Sales", "TechFlow CRM add-on", "TechFlow", 15000, "Pipeline analytics", Urgency.ROUTINE),
        ("Alex Rivera", "Engineering", "CloudBase dev envs", "CloudBase Inc", 19000, "New hire onboarding", Urgency.ROUTINE),
    ]
    return [
        PurchaseRequest(
            id=f"PR-{i + 1:03d}",
            requester=requester,
            department=department,
            item=item,
            vendor=vendor,
            amount=amount,
            justification=justification,
            urgency=urgency,
            status=RequestStatus.PENDING,
            created_at=_BASE_TS + timedelta(hours=i * 2),
            updated_at=_BASE_TS + timedelta(hours=i * 2),
        )
        for i, (requester, department, item, vendor, amount, justification, urgency) in enumerate(fields)
    ]


CURATED_TEST_REQUESTS: list[PurchaseRequest] = _build()
"""10 deterministic test requests, IDs PR-001..PR-010."""
