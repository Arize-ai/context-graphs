from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.database import get_connection, insert_purchase_request
from src.models import (
    Confidence,
    EvaluatorAssessment,
    PolicyCompliance,
    PurchaseRequest,
    Recommendation,
)
from src.seed_data import seed
from tests.fixtures import CURATED_TEST_REQUESTS

# `seed()` populates only reference data; tests that need request history
# insert curated test requests directly so their assertions stay deterministic.
SEEDED_REQUEST_COUNT = len(CURATED_TEST_REQUESTS)
NEXT_ID_AFTER_SEED = f"PR-{SEEDED_REQUEST_COUNT + 1:03d}"


def _fake_assessment(request_id: str) -> EvaluatorAssessment:
    return EvaluatorAssessment(
        request_id=request_id,
        policy_compliance=PolicyCompliance.COMPLIANT,
        policy_details="auto-approved",
        budget_status="ok",
        vendor_status="approved",
        recommendation=Recommendation.APPROVE,
        recommendation_reasoning="passes policy",
        confidence=Confidence.HIGH,
    )


def _seeded_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    seed(conn)
    for req in CURATED_TEST_REQUESTS:
        insert_purchase_request(conn, req)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def client(tmp_path: Path):
    db_path = _seeded_db_path(tmp_path)
    with patch("src.main.get_connection", lambda: get_connection(db_path)):
        from src.main import app
        yield TestClient(app)


@pytest.fixture()
def client_with_mocked_agent(tmp_path: Path):
    """Client whose create endpoint sees a stub evaluator instead of OpenAI."""
    db_path = _seeded_db_path(tmp_path)
    with patch("src.main.get_connection", lambda: get_connection(db_path)), patch(
        "src.agent.pipeline.run_evaluator",
        side_effect=lambda conn, req, model="gpt-4o-mini", override=None: _fake_assessment(req.id),
    ):
        from src.main import app
        yield TestClient(app)


class TestListRequests:
    def test_returns_all_seeded(self, client: TestClient):
        resp = client.get("/api/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == SEEDED_REQUEST_COUNT
        ids = {r["id"] for r in data}
        assert "PR-001" in ids

    def test_get_single_request(self, client: TestClient):
        resp = client.get("/api/requests/PR-005")
        assert resp.status_code == 200
        assert resp.json()["vendor"] == "FreshStack"

    def test_get_nonexistent_returns_404(self, client: TestClient):
        resp = client.get("/api/requests/PR-999")
        assert resp.status_code == 404


class TestCreateRequest:
    def test_create_assigns_next_id(self, client_with_mocked_agent: TestClient):
        resp = client_with_mocked_agent.post("/api/requests", json={
            "requester": "Test User",
            "department": "Engineering",
            "item": "Test item",
            "vendor": "TechFlow",
            "amount": 500,
            "justification": "Testing",
            "urgency": "routine",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == NEXT_ID_AFTER_SEED
        # Auto-process: status should be 'completed', not 'pending'.
        assert data["status"] == "completed"

    def test_create_runs_agent_and_persists_assessment(
        self, client_with_mocked_agent: TestClient
    ):
        resp = client_with_mocked_agent.post("/api/requests", json={
            "requester": "Test User",
            "department": "Engineering",
            "item": "Auto-processed item",
            "vendor": "TechFlow",
            "amount": 750,
            "justification": "Verify auto-process flow",
            "urgency": "routine",
        })
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        # An assessment should now exist for the new request.
        assessments = client_with_mocked_agent.get(
            f"/api/requests/{new_id}/assessments"
        ).json()
        assert len(assessments) == 1
        assert assessments[0]["assessment"]["recommendation"] == "approve"
        assert assessments[0]["assessment"]["request_id"] == new_id

    def test_create_persists(self, client_with_mocked_agent: TestClient):
        client_with_mocked_agent.post("/api/requests", json={
            "requester": "Test User",
            "department": "Engineering",
            "item": "Persisted item",
            "vendor": "TechFlow",
            "amount": 100,
            "justification": "Persistence test",
            "urgency": "urgent",
        })
        resp = client_with_mocked_agent.get(f"/api/requests/{NEXT_ID_AFTER_SEED}")
        assert resp.status_code == 200
        assert resp.json()["item"] == "Persisted item"
        assert resp.json()["urgency"] == "urgent"

    def test_create_sequential_ids(self, client_with_mocked_agent: TestClient):
        for i in range(3):
            resp = client_with_mocked_agent.post("/api/requests", json={
                "requester": "User",
                "department": "Engineering",
                "item": f"Item {i}",
                "vendor": "TechFlow",
                "amount": 100,
                "justification": "J",
                "urgency": "routine",
            })
            assert resp.json()["id"] == f"PR-{SEEDED_REQUEST_COUNT + 1 + i:03d}"

    def test_create_missing_field_returns_422(self, client: TestClient):
        # Validation runs before the agent — no mock needed here.
        resp = client.post("/api/requests", json={
            "requester": "Test User",
            "department": "Engineering",
        })
        assert resp.status_code == 422

    def test_create_empty_requester_returns_422(self, client: TestClient):
        resp = client.post("/api/requests", json={
            "requester": "",
            "department": "Engineering",
            "item": "Item",
            "vendor": "TechFlow",
            "amount": 100,
            "justification": "J",
            "urgency": "routine",
        })
        assert resp.status_code == 422

    def test_create_invalid_urgency_returns_422(self, client: TestClient):
        resp = client.post("/api/requests", json={
            "requester": "User",
            "department": "Engineering",
            "item": "Item",
            "vendor": "TechFlow",
            "amount": 100,
            "justification": "J",
            "urgency": "critical",
        })
        assert resp.status_code == 422

    def test_agent_failure_leaves_request_pending(self, tmp_path: Path):
        """If the agent raises during create, the request stays at PENDING."""
        db_path = _seeded_db_path(tmp_path)
        with patch("src.main.get_connection", lambda: get_connection(db_path)), patch(
            "src.agent.pipeline.run_evaluator",
            side_effect=RuntimeError("LLM down"),
        ):
            from src.main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/requests", json={
                "requester": "Test",
                "department": "Engineering",
                "item": "Will fail",
                "vendor": "TechFlow",
                "amount": 100,
                "justification": "J",
                "urgency": "routine",
            })
            assert resp.status_code == 500
            # The request should still exist, in PENDING state.
            row = client.get(f"/api/requests/{NEXT_ID_AFTER_SEED}")
            assert row.status_code == 200
            assert row.json()["status"] == "pending"


class TestListDepartmentsAndVendors:
    def test_departments(self, client: TestClient):
        resp = client.get("/api/departments")
        assert resp.status_code == 200
        names = {d["name"] for d in resp.json()}
        assert names == {"Engineering", "Marketing", "Customer Success", "Sales", "Security"}

    def test_vendors(self, client: TestClient):
        resp = client.get("/api/vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 9
        techflow = next(v for v in data if v["name"] == "TechFlow")
        assert techflow["status"] == "preferred"
