import pytest
from pydantic import ValidationError

from datetime import datetime

from src.models import (
    AssessmentRecord,
    Confidence,
    Department,
    EvaluatorAssessment,
    Policy,
    PolicyCompliance,
    PurchaseRequest,
    PurchaseRequestCreate,
    Recommendation,
    RequestStatus,
    ReviewDecision,
    ReviewerDecision,
    Urgency,
    Vendor,
    VendorStatus,
)


class TestDepartment:
    def test_valid(self):
        dept = Department(name="Engineering", headcount=50, quarterly_budget=200_000)
        assert dept.name == "Engineering"
        assert dept.headcount == 50
        assert dept.quarterly_budget == 200_000

    def test_headcount_must_be_positive(self):
        with pytest.raises(ValidationError):
            Department(name="X", headcount=0, quarterly_budget=1000)

    def test_budget_must_be_positive(self):
        with pytest.raises(ValidationError):
            Department(name="X", headcount=1, quarterly_budget=-100)


class TestVendor:
    def test_valid(self):
        v = Vendor(name="TechFlow", status=VendorStatus.PREFERRED, categories=["software"])
        assert v.status == VendorStatus.PREFERRED
        assert v.notes == ""

    def test_with_notes(self):
        v = Vendor(name="CloudBase", status=VendorStatus.APPROVED, categories=["cloud"], notes="SLA issues")
        assert v.notes == "SLA issues"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            Vendor(name="X", status="unknown", categories=[])

    def test_all_statuses(self):
        for status in VendorStatus:
            v = Vendor(name="V", status=status, categories=["cat"])
            assert v.status == status


class TestPolicy:
    def test_valid(self):
        p = Policy(name="Software", description="Thresholds", rules=["rule1", "rule2"])
        assert len(p.rules) == 2

    def test_empty_rules(self):
        p = Policy(name="Empty", description="No rules", rules=[])
        assert p.rules == []


class TestPurchaseRequest:
    def test_valid(self):
        pr = PurchaseRequest(
            id="PR-001",
            requester="Alex",
            department="Engineering",
            item="Licenses",
            vendor="TechFlow",
            amount=3200,
            justification="Need them",
            urgency=Urgency.ROUTINE,
        )
        assert pr.status == RequestStatus.PENDING

    def test_id_pattern_valid(self):
        PurchaseRequest(
            id="PR-030",
            requester="X",
            department="D",
            item="I",
            vendor="V",
            amount=1,
            justification="J",
            urgency="routine",
        )

    def test_id_pattern_invalid_no_prefix(self):
        with pytest.raises(ValidationError):
            PurchaseRequest(
                id="001",
                requester="X",
                department="D",
                item="I",
                vendor="V",
                amount=1,
                justification="J",
                urgency="routine",
            )

    def test_id_pattern_invalid_too_many_digits(self):
        with pytest.raises(ValidationError):
            PurchaseRequest(
                id="PR-0001",
                requester="X",
                department="D",
                item="I",
                vendor="V",
                amount=1,
                justification="J",
                urgency="routine",
            )

    def test_invalid_urgency(self):
        with pytest.raises(ValidationError):
            PurchaseRequest(
                id="PR-001",
                requester="X",
                department="D",
                item="I",
                vendor="V",
                amount=1,
                justification="J",
                urgency="critical",
            )

    def test_urgency_from_string(self):
        pr = PurchaseRequest(
            id="PR-001",
            requester="X",
            department="D",
            item="I",
            vendor="V",
            amount=1,
            justification="J",
            urgency="emergency",
        )
        assert pr.urgency == Urgency.EMERGENCY

    def test_negative_amount_allowed(self):
        """PR-027 is a credit/refund with negative amount."""
        pr = PurchaseRequest(
            id="PR-027",
            requester="Priya",
            department="Marketing",
            item="Seat reduction",
            vendor="CreativeHub",
            amount=-3000,
            justification="Reducing seats",
            urgency="routine",
        )
        assert pr.amount == -3000

    def test_default_status_is_pending(self):
        pr = PurchaseRequest(
            id="PR-001",
            requester="X",
            department="D",
            item="I",
            vendor="V",
            amount=1,
            justification="J",
            urgency="routine",
        )
        assert pr.status == RequestStatus.PENDING

    def test_explicit_status(self):
        pr = PurchaseRequest(
            id="PR-001",
            requester="X",
            department="D",
            item="I",
            vendor="V",
            amount=1,
            justification="J",
            urgency="routine",
            status=RequestStatus.COMPLETED,
        )
        assert pr.status == RequestStatus.COMPLETED


class TestPurchaseRequestCreate:
    def test_valid(self):
        body = PurchaseRequestCreate(
            requester="Alex",
            department="Engineering",
            item="Licenses",
            vendor="TechFlow",
            amount=3200,
            justification="Need them",
            urgency="routine",
        )
        assert body.urgency == Urgency.ROUTINE

    def test_empty_requester_rejected(self):
        with pytest.raises(ValidationError):
            PurchaseRequestCreate(
                requester="",
                department="Engineering",
                item="Licenses",
                vendor="TechFlow",
                amount=3200,
                justification="Need them",
                urgency="routine",
            )

    def test_empty_item_rejected(self):
        with pytest.raises(ValidationError):
            PurchaseRequestCreate(
                requester="Alex",
                department="Engineering",
                item="",
                vendor="TechFlow",
                amount=3200,
                justification="Need them",
                urgency="routine",
            )

    def test_no_id_or_status_fields(self):
        """PurchaseRequestCreate should not accept id or status."""
        body = PurchaseRequestCreate(
            requester="Alex",
            department="Engineering",
            item="Licenses",
            vendor="TechFlow",
            amount=100,
            justification="J",
            urgency="routine",
        )
        assert not hasattr(body, "id") or "id" not in body.model_fields
        assert not hasattr(body, "status") or "status" not in body.model_fields


class TestEvaluatorAssessment:
    def test_valid(self):
        a = EvaluatorAssessment(
            request_id="PR-001",
            policy_compliance="compliant",
            policy_details="Within threshold",
            budget_status="Available",
            vendor_status="Approved",
            duplicate_check="None found",
            history_notes="No history",
            recommendation="approve",
            recommendation_reasoning="All clear",
            confidence="high",
            risk_factors=[],
        )
        assert a.policy_compliance == PolicyCompliance.COMPLIANT
        assert a.recommendation == Recommendation.APPROVE

    def test_risk_factors_default_empty(self):
        a = EvaluatorAssessment(
            request_id="PR-001",
            policy_compliance="compliant",
            policy_details="OK",
            budget_status="OK",
            vendor_status="OK",
            duplicate_check="OK",
            history_notes="OK",
            recommendation="approve",
            recommendation_reasoning="OK",
            confidence="high",
        )
        assert a.risk_factors == []


class TestReviewDecision:
    def test_valid_override(self):
        rd = ReviewDecision(
            request_id="PR-001",
            agent_recommendation="approve",
            reviewer_decision="reject",
            override=True,
            reasoning="Vendor suspended",
            confidence="high",
        )
        assert rd.override is True
        assert rd.reviewer_decision == ReviewerDecision.REJECT

    def test_valid_agreement(self):
        rd = ReviewDecision(
            request_id="PR-001",
            agent_recommendation="approve",
            reviewer_decision="approve",
            override=False,
            reasoning="Agreed",
            confidence="high",
        )
        assert rd.override is False


class TestAssessmentRecord:
    def _assessment(self) -> EvaluatorAssessment:
        return EvaluatorAssessment(
            request_id="PR-001",
            policy_compliance="compliant",
            policy_details="OK",
            budget_status="OK",
            vendor_status="OK",
            duplicate_check="OK",
            history_notes="OK",
            recommendation="approve",
            recommendation_reasoning="OK",
            confidence="high",
        )

    def test_defaults_to_no_review(self):
        record = AssessmentRecord(
            request_id="PR-001",
            session_id="abc-123",
            assessment=self._assessment(),
        )
        assert record.session_id == "abc-123"
        assert record.review is None
        assert record.reviewed_at is None
        assert record.created_at is not None

    def test_with_review_attached(self):
        review = ReviewDecision(
            request_id="PR-001",
            agent_recommendation="approve",
            reviewer_decision="reject",
            override=True,
            reasoning="Vendor suspended",
            confidence="high",
        )
        record = AssessmentRecord(
            request_id="PR-001",
            session_id="abc-123",
            assessment=self._assessment(),
            review=review,
            reviewed_at=datetime(2026, 4, 19, 9, 0, 0),
        )
        assert record.review is not None
        assert record.review.override is True
        assert record.reviewed_at == datetime(2026, 4, 19, 9, 0, 0)
