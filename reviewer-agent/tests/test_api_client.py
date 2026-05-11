"""Tests for the reviewer's HTTP client.

Mocks `httpx.Client` so the suite runs without a live agent — the goal is
to verify URL + payload shape, not to exercise the agent itself.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.api_client import AgentClient
from src.models import (
    Confidence,
    HumanOverride,
    Recommendation,
    ReviewDecision,
    ReviewerDecision,
)


def _ok_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture()
def client(monkeypatch):
    c = AgentClient(base_url="http://test")
    fake_http = MagicMock()
    monkeypatch.setattr(c, "_client", fake_http)
    return c, fake_http


def _assessment_record_json(request_id: str = "PR-001") -> dict:
    return {
        "request_id": request_id,
        "session_id": "sess-1",
        "assessment": {
            "request_id": request_id,
            "policy_compliance": "compliant",
            "policy_details": "",
            "budget_status": "",
            "vendor_status": "",
            "duplicate_check": "",
            "history_notes": "",
            "recommendation": "approve",
            "recommendation_reasoning": "",
            "confidence": "high",
            "risk_factors": [],
        },
        "review": None,
        "created_at": datetime(2026, 4, 29, 10, 0, 0).isoformat(),
        "reviewed_at": None,
    }


class TestOverride:
    def test_posts_to_correct_url_with_full_body(self, client):
        c, http = client
        http.post.return_value = _ok_response(_assessment_record_json("PR-001"))

        body = HumanOverride(
            decision=ReviewerDecision.REJECT,
            reasoning="Vendor suspended",
            reviewer_name="Vera Fye",
            precedent_applied="DT-0007",
            conditions="Resolve billing first",
            confidence=Confidence.HIGH,
        )
        c.override("PR-001", body)

        http.post.assert_called_once()
        url, kwargs = http.post.call_args.args[0], http.post.call_args.kwargs
        assert url == "/api/requests/PR-001/override"
        assert kwargs["json"] == {
            "decision": "reject",
            "reasoning": "Vendor suspended",
            "reviewer_name": "Vera Fye",
            "precedent_applied": "DT-0007",
            "conditions": "Resolve billing first",
            "confidence": "high",
        }

    def test_minimal_body_uses_defaults(self, client):
        c, http = client
        http.post.return_value = _ok_response(_assessment_record_json())

        c.override(
            "PR-002",
            HumanOverride(decision=ReviewerDecision.APPROVE, reasoning="ok"),
        )

        sent = http.post.call_args.kwargs["json"]
        assert sent["reviewer_name"] == ""
        assert sent["precedent_applied"] == ""
        assert sent["conditions"] == ""
        assert sent["confidence"] == "high"


class TestAttachReviewLegacy:
    """attach_review remains for non-traced direct attaches."""

    def test_posts_to_assessment_session_endpoint(self, client):
        c, http = client
        http.post.return_value = _ok_response(_assessment_record_json())

        review = ReviewDecision(
            request_id="PR-001",
            agent_recommendation=Recommendation.APPROVE,
            reviewer_decision=ReviewerDecision.REJECT,
            override=True,
            reasoning="x",
            confidence=Confidence.HIGH,
        )
        c.attach_review("sess-xyz", review)

        url = http.post.call_args.args[0]
        assert url == "/api/assessments/sess-xyz/review"
