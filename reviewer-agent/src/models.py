"""Pydantic models for the reviewer.

These mirror the shape of the procurement-agent's API responses but are owned
locally — the reviewer is a separate app that depends only on the wire contract
(JSON shape) of the agent's HTTP API, not on its source code.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Urgency(StrEnum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class RequestStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"


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


class ReviewerDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    FLAG_FOR_REVIEW = "flag-for-review"


class PurchaseRequest(BaseModel):
    id: str
    requester: str
    department: str
    item: str
    vendor: str
    amount: float
    justification: str
    urgency: Urgency
    status: RequestStatus
    created_at: datetime
    updated_at: datetime


class EvaluatorAssessment(BaseModel):
    request_id: str
    policy_compliance: PolicyCompliance
    policy_details: str
    budget_status: str
    vendor_status: str
    duplicate_check: str
    history_notes: str
    recommendation: Recommendation
    recommendation_reasoning: str
    confidence: Confidence
    risk_factors: list[str] = []


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
    """Body for `POST /api/requests/{id}/override`.

    The reviewer sends Vera's full decision package; the agent re-runs
    with this as additional input (visible in the Arize trace) and
    persists the corresponding `ReviewDecision` against the new
    assessment it produces. Mirrors the agent's `HumanOverride`.
    """

    decision: ReviewerDecision
    reasoning: str
    reviewer_name: str = ""
    precedent_applied: str = ""
    conditions: str = ""
    confidence: Confidence = Confidence.HIGH


class AssessmentRecord(BaseModel):
    request_id: str
    session_id: str
    assessment: EvaluatorAssessment
    review: ReviewDecision | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
