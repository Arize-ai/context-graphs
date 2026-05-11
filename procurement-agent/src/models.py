"""Pydantic models for the procurement domain.

Defines reference data (`Department`, `Vendor`, `Policy`), the request
itself (`PurchaseRequest`), and the agent + reviewer outputs
(`EvaluatorAssessment`, `ReviewDecision`, `AssessmentRecord`). The same
shapes are mirrored in `procurement-agent/ui/src/lib/types.ts` and in
`reviewer-agent/src/models.py`; field names and enum values must
stay in sync across all three.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VendorStatus(StrEnum):
    PREFERRED = "preferred"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    NOT_LISTED = "not_listed"


class Urgency(StrEnum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class RequestStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"


class Department(BaseModel):
    name: str
    headcount: int = Field(gt=0)
    quarterly_budget: float = Field(gt=0)
    # Inert default — populated only by an active experiment variant. With no
    # variant loaded, this stays empty and `lookup_department` returns
    # "no behavior data available", which is byte-identical to the baseline
    # agent's behavior (no department-behavior tool was previously surfaced).
    behavior_notes: list[str] = []


class Vendor(BaseModel):
    name: str
    status: VendorStatus
    categories: list[str]
    notes: str = ""
    # Inert defaults — populated only by an active experiment variant. The
    # `lookup_vendor` tool surfaces these only when they differ from defaults,
    # so the baseline agent sees exactly what it saw before.
    cost_overrun_factor: float = 1.0
    relationship_credit: str = ""
    deprecating_in_favor_of: str | None = None


class Policy(BaseModel):
    name: str
    description: str
    rules: list[str]


class PurchaseRequest(BaseModel):
    id: str = Field(pattern=r"^PR-\d{3}$")
    requester: str
    department: str
    item: str
    vendor: str
    amount: float
    justification: str
    urgency: Urgency
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


class PurchaseRequestCreate(BaseModel):
    requester: str = Field(min_length=1)
    department: str = Field(min_length=1)
    item: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    amount: float
    justification: str = Field(min_length=1)
    urgency: Urgency


class PolicyCompliance(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non-compliant"
    EDGE_CASE = "edge-case"


class Recommendation(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    FLAG_FOR_REVIEW = "flag-for-review"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvaluatorAssessment(BaseModel):
    """Structured output from the evaluator agent.

    `request_id`, `policy_compliance`, and `recommendation` are the load-
    bearing fields and remain required — they're what the UI's tab routing
    and the trace-mining downstream depend on. Every other field defaults
    to empty so a flaky LLM omission doesn't block the whole assessment;
    the worst case is a sparser-than-ideal record, not a failed request.
    """

    request_id: str
    policy_compliance: PolicyCompliance
    policy_details: str = ""
    budget_status: str = ""
    vendor_status: str = ""
    duplicate_check: str = ""
    history_notes: str = ""
    recommendation: Recommendation
    recommendation_reasoning: str = ""
    confidence: Confidence = Confidence.MEDIUM
    risk_factors: list[str] = []

    @field_validator("duplicate_check", "history_notes", mode="before")
    @classmethod
    def _coerce_empty_to_str(cls, v: Any) -> Any:
        # LLMs occasionally emit `null` or `[]` for these "no info" fields
        # despite the schema declaring them as strings — normalise both
        # shapes to the empty string so structured-output validation passes.
        if v is None:
            return ""
        if isinstance(v, (list, dict)) and not v:
            return ""
        return v


class ReviewerDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    FLAG_FOR_REVIEW = "flag-for-review"


class ReviewDecision(BaseModel):
    request_id: str
    agent_recommendation: Recommendation
    reviewer_decision: ReviewerDecision
    reviewer_name: str = ""
    override: bool
    reasoning: str
    precedent_applied: str = ""
    conditions: str = ""
    confidence: Confidence


class HumanOverride(BaseModel):
    """Body of an override request — the reviewer's full decision package.

    Threaded into the agent prompt so the override appears in the trace
    and the agent can produce a fresh structured assessment that
    incorporates the human's input. Used by both the UI's override form
    and the reviewer-agent CLI.

    `reviewer_name` is required so every traced override is attributable
    to a specific person. Other rich fields (`precedent_applied`,
    `conditions`, `confidence`) are optional.
    """

    decision: ReviewerDecision
    reasoning: str
    reviewer_name: str = ""
    precedent_applied: str = ""
    conditions: str = ""
    confidence: Confidence = Confidence.HIGH


class AssessmentRecord(BaseModel):
    """An evaluator's assessment of a request, with an optional later human review.

    The agent runs the evaluator and produces an AssessmentRecord with review=None.
    A review may be attached later via `POST /api/assessments/{session_id}/review`,
    capturing human feedback as an independent step in the workflow.

    `span_id` (optional) is the 16-char hex id of the CHAIN root span the agent
    emitted for this run. Returned from the API so experiment runners can push
    per-row annotations (e.g. evaluator scores) onto the right span.
    """

    request_id: str
    session_id: str
    assessment: EvaluatorAssessment
    review: ReviewDecision | None = None
    span_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    reviewed_at: datetime | None = None
