"""Integration tests for POST /api/requests/{id}/process.

The agent's LLM call is mocked so the full HTTP → DB → assessment path can
be exercised without a network call. The mock is patched at the import site
in `src.agent.pipeline`, which is where `process_request` looks up
`run_evaluator`.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.database import get_connection, insert_purchase_request
from src.models import (
    Confidence,
    EvaluatorAssessment,
    PolicyCompliance,
    Recommendation,
)
from src.seed_data import seed
from tests.fixtures import CURATED_TEST_REQUESTS


def _fake_assessment(request_id: str) -> EvaluatorAssessment:
    return EvaluatorAssessment(
        request_id=request_id,
        policy_compliance=PolicyCompliance.COMPLIANT,
        policy_details="manager approval needed",
        budget_status="Budget available",
        vendor_status="approved",
        recommendation=Recommendation.FLAG_FOR_REVIEW,
        recommendation_reasoning="needs manager sign-off",
        confidence=Confidence.HIGH,
        risk_factors=["test risk"],
    )


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    seed(conn)
    # seed() no longer inserts requests; tests exercise PR-001+ so insert
    # the curated set directly here to keep the fixture stable.
    for req in CURATED_TEST_REQUESTS:
        insert_purchase_request(conn, req)
    conn.commit()
    conn.close()

    with patch("src.main.get_connection", lambda: get_connection(db_path)):
        from src.main import app
        yield TestClient(app)


class TestProcessEndpoint:
    def test_returns_assessment_record(self, client: TestClient):
        with patch(
            "src.agent.pipeline.run_evaluator",
            side_effect=lambda conn, req, model="claude-haiku-4-5", override=None: _fake_assessment(req.id),
        ):
            resp = client.post("/api/requests/PR-001/process")
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == "PR-001"
        assert body["session_id"]  # uuid present
        assert body["assessment"]["recommendation"] == "flag-for-review"
        assert body["review"] is None

    def test_persists_assessment(self, client: TestClient):
        with patch(
            "src.agent.pipeline.run_evaluator",
            side_effect=lambda conn, req, model="claude-haiku-4-5", override=None: _fake_assessment(req.id),
        ):
            client.post("/api/requests/PR-001/process")

        resp = client.get("/api/requests/PR-001/assessments")
        assert resp.status_code == 200
        assessments = resp.json()
        assert len(assessments) == 1
        assert assessments[0]["assessment"]["recommendation"] == "flag-for-review"

    def test_request_status_transitions_to_completed(self, client: TestClient):
        with patch(
            "src.agent.pipeline.run_evaluator",
            side_effect=lambda conn, req, model="claude-haiku-4-5", override=None: _fake_assessment(req.id),
        ):
            client.post("/api/requests/PR-001/process")

        resp = client.get("/api/requests/PR-001")
        assert resp.json()["status"] == "completed"

    def test_unknown_request_returns_404(self, client: TestClient):
        resp = client.post("/api/requests/PR-999/process")
        assert resp.status_code == 404

    def test_override_runs_agent_and_attaches_review(self, client: TestClient):
        """POST /override re-runs the agent with the override and attaches a review."""
        captured: dict = {}

        def fake_eval(conn, req, model="claude-haiku-4-5", override=None):
            captured["override"] = override
            # Mirror the override decision in the recommendation so the
            # endpoint's `override` flag computation is exercised against a
            # known prior recommendation.
            from src.models import Recommendation
            rec = Recommendation(override.decision.value) if override else Recommendation.APPROVE
            return _fake_assessment(req.id).model_copy(update={"recommendation": rec})

        with patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval):
            # First, produce an initial assessment (recommendation = approve)
            client.post("/api/requests/PR-001/process")
            # Then override it to reject
            resp = client.post(
                "/api/requests/PR-001/override",
                json={"decision": "reject", "reasoning": "vendor SLA concerns"},
            )
        assert resp.status_code == 200
        body = resp.json()
        # New assessment was produced
        assert body["request_id"] == "PR-001"
        assert body["session_id"]
        # Review attached, override flag set because reviewer disagreed with prior
        assert body["review"] is not None
        assert body["review"]["reviewer_decision"] == "reject"
        assert body["review"]["agent_recommendation"] == "approve"
        assert body["review"]["override"] is True
        assert body["review"]["reasoning"] == "vendor SLA concerns"
        # Override was forwarded to the agent (visible in trace input)
        assert captured["override"] is not None
        assert captured["override"].decision.value == "reject"
        assert captured["override"].reasoning == "vendor SLA concerns"

    def test_override_threads_full_signal_into_agent_and_review(self, client: TestClient):
        """precedent_applied, conditions, and confidence flow into both the
        agent prompt (visible in the trace) and the persisted ReviewDecision."""
        captured: dict = {}

        def fake_eval(conn, req, model="claude-haiku-4-5", override=None):
            captured["override"] = override
            from src.models import Recommendation
            rec = Recommendation(override.decision.value) if override else Recommendation.APPROVE
            return _fake_assessment(req.id).model_copy(update={"recommendation": rec})

        with patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval):
            client.post("/api/requests/PR-001/process")
            resp = client.post(
                "/api/requests/PR-001/override",
                json={
                    "decision": "reject",
                    "reasoning": "Insight Partners suspended after 2024 billing dispute",
                    "reviewer_name": "Vera Fye",
                    "precedent_applied": "Q1 Insight Partners rejection",
                    "conditions": "Reject all Insight Partners requests until billing dispute resolved",
                    "confidence": "high",
                },
            )
        assert resp.status_code == 200
        review = resp.json()["review"]
        assert review["reviewer_name"] == "Vera Fye"
        assert review["precedent_applied"] == "Q1 Insight Partners rejection"
        assert review["conditions"].startswith("Reject all Insight Partners")
        assert review["confidence"] == "high"

        ov = captured["override"]
        assert ov.reviewer_name == "Vera Fye"
        assert ov.precedent_applied == "Q1 Insight Partners rejection"
        assert ov.conditions.startswith("Reject all Insight Partners")
        assert ov.confidence.value == "high"

    def test_override_pushes_annotation_to_root_span(self, client: TestClient):
        """The override endpoint must call apply_override_annotation with the
        root span id and the full HumanOverride body. Tracing is active
        (conftest installs a TracerProvider) so root_span_id is non-None."""
        captured: dict = {}

        def fake_eval(conn, req, model="claude-haiku-4-5", override=None):
            from src.models import Recommendation
            rec = Recommendation(override.decision.value) if override else Recommendation.APPROVE
            return _fake_assessment(req.id).model_copy(update={"recommendation": rec})

        def fake_apply(span_id, body):
            captured["span_id"] = span_id
            captured["body"] = body
            return True

        with patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval), \
             patch("src.annotations.apply_override_annotation", side_effect=fake_apply):
            client.post("/api/requests/PR-001/process")
            resp = client.post(
                "/api/requests/PR-001/override",
                json={
                    "decision": "reject",
                    "reasoning": "Vendor suspended",
                    "reviewer_name": "Vera Fye",
                    "precedent_applied": "Q1 Insight Partners rejection",
                    "conditions": "Until billing resolved",
                    "confidence": "high",
                },
            )
        assert resp.status_code == 200
        # Annotation was invoked with the override body intact.
        assert captured["body"].decision.value == "reject"
        assert captured["body"].reviewer_name == "Vera Fye"
        assert captured["body"].precedent_applied == "Q1 Insight Partners rejection"
        assert isinstance(captured["span_id"], str)
        assert len(captured["span_id"]) == 16

    def test_override_succeeds_when_annotation_fails(self, client: TestClient):
        """If the annotation push raises, the override must still succeed —
        the persisted ReviewDecision is the durable record."""
        def fake_eval(conn, req, model="claude-haiku-4-5", override=None):
            from src.models import Recommendation
            rec = Recommendation(override.decision.value) if override else Recommendation.APPROVE
            return _fake_assessment(req.id).model_copy(update={"recommendation": rec})

        def boom(span_id, body):
            raise RuntimeError("Arize is down")

        with patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval), \
             patch("src.annotations.apply_override_annotation", side_effect=boom):
            client.post("/api/requests/PR-001/process")
            resp = client.post(
                "/api/requests/PR-001/override",
                json={"decision": "approve", "reasoning": "ok", "reviewer_name": "x"},
            )
        # Override still succeeds — the persisted ReviewDecision is the
        # durable record; an annotation push failure must not surface.
        assert resp.status_code == 200
        assert resp.json()["review"] is not None

    def test_override_unknown_request_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/requests/PR-999/override",
            json={"decision": "approve", "reasoning": "x"},
        )
        assert resp.status_code == 404

    def test_evaluator_failure_rolls_back(self, tmp_path: Path):
        """If the agent raises, the request status must not be left at PROCESSING."""
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        seed(conn)
        for req in CURATED_TEST_REQUESTS:
            insert_purchase_request(conn, req)
        conn.commit()
        conn.close()

        with patch("src.main.get_connection", lambda: get_connection(db_path)):
            from src.main import app
            # raise_server_exceptions=False so TestClient returns 500 instead of re-raising
            client = TestClient(app, raise_server_exceptions=False)

            with patch(
                "src.agent.pipeline.run_evaluator",
                side_effect=RuntimeError("LLM unavailable"),
            ):
                resp = client.post("/api/requests/PR-001/process")
            assert resp.status_code == 500
            status = client.get("/api/requests/PR-001").json()["status"]
            assert status != "processing"
