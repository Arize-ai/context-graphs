from datetime import datetime

from src.models import (
    AssessmentRecord,
    Confidence,
    EvaluatorAssessment,
    HumanOverride,
    PolicyCompliance,
    PurchaseRequest,
    Recommendation,
    RequestStatus,
    ReviewDecision,
    ReviewerDecision,
    Urgency,
)


def _assessment() -> EvaluatorAssessment:
    return EvaluatorAssessment(
        request_id="PR-001",
        policy_compliance=PolicyCompliance.COMPLIANT,
        policy_details="OK",
        budget_status="OK",
        vendor_status="OK",
        duplicate_check="OK",
        history_notes="OK",
        recommendation=Recommendation.APPROVE,
        recommendation_reasoning="OK",
        confidence=Confidence.HIGH,
    )


def test_purchase_request_parses_iso_timestamps():
    pr = PurchaseRequest.model_validate(
        {
            "id": "PR-001",
            "requester": "Alex",
            "department": "Engineering",
            "item": "Licenses",
            "vendor": "TechFlow",
            "amount": 3200,
            "justification": "Need them",
            "urgency": "routine",
            "status": "pending",
            "created_at": "2026-04-29T10:00:00",
            "updated_at": "2026-04-29T10:00:00",
        }
    )
    assert pr.urgency == Urgency.ROUTINE
    assert pr.status == RequestStatus.PENDING
    assert pr.created_at == datetime(2026, 4, 29, 10, 0, 0)


def test_assessment_record_review_is_optional():
    record = AssessmentRecord(
        request_id="PR-001",
        session_id="abc",
        assessment=_assessment(),
        created_at=datetime(2026, 4, 29, 10, 0, 0),
    )
    assert record.review is None
    assert record.reviewed_at is None


def test_human_override_minimum_payload_serializes_with_defaults():
    body = HumanOverride(decision=ReviewerDecision.APPROVE, reasoning="agree with agent")
    payload = body.model_dump(mode="json")
    assert payload == {
        "decision": "approve",
        "reasoning": "agree with agent",
        "reviewer_name": "",
        "precedent_applied": "",
        "conditions": "",
        "confidence": "high",
    }


def test_human_override_carries_full_signal():
    body = HumanOverride(
        decision=ReviewerDecision.REJECT,
        reasoning="vendor suspended after 2024 dispute",
        reviewer_name="Vera Fye",
        precedent_applied="DT-0007",
        conditions="reject until billing dispute resolved",
        confidence=Confidence.HIGH,
    )
    payload = body.model_dump(mode="json")
    assert payload["reviewer_name"] == "Vera Fye"
    assert payload["precedent_applied"] == "DT-0007"
    assert payload["conditions"].startswith("reject until")
    assert payload["confidence"] == "high"


def test_assessment_record_with_review():
    review = ReviewDecision(
        request_id="PR-001",
        agent_recommendation=Recommendation.APPROVE,
        reviewer_decision=ReviewerDecision.REJECT,
        override=True,
        reasoning="Vendor suspended",
        confidence=Confidence.HIGH,
    )
    record = AssessmentRecord(
        request_id="PR-001",
        session_id="abc",
        assessment=_assessment(),
        review=review,
        created_at=datetime(2026, 4, 29, 10, 0, 0),
        reviewed_at=datetime(2026, 4, 29, 11, 0, 0),
    )
    assert record.review.override is True
