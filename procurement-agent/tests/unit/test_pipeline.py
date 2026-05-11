"""Tests for src/agent/pipeline.process_request.

Mocks `run_evaluator` so the pipeline can be tested without a live LLM. The
key invariants checked here are:

- A fresh `session_id` UUID is minted per call (used by the review endpoint
  to address one specific assessment).
- The pipeline opens an `openinference.instrumentation.using_attributes`
  context with `session_id = request.id` around the evaluator call, so all
  agent runs for the same purchase request group into one Arize session.
  (The actual span-attribute propagation is done by LangChainInstrumentor
  reading from OTel context — that's the instrumentor's contract, not the
  pipeline's, so we verify the call shape, not the resulting span tags.)
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.agent.pipeline import process_request
from src.models import (
    Confidence,
    EvaluatorAssessment,
    HumanOverride,
    PolicyCompliance,
    PurchaseRequest,
    Recommendation,
    ReviewerDecision,
    Urgency,
)


def _fake_assessment(request_id: str) -> EvaluatorAssessment:
    return EvaluatorAssessment(
        request_id=request_id,
        policy_compliance=PolicyCompliance.COMPLIANT,
        policy_details="x",
        budget_status="ok",
        vendor_status="approved",
        recommendation=Recommendation.APPROVE,
        recommendation_reasoning="r",
        confidence=Confidence.HIGH,
    )


def _make_request(request_id: str = "PR-001") -> PurchaseRequest:
    return PurchaseRequest(
        id=request_id,
        requester="Test",
        department="Engineering",
        item="Test item",
        vendor="TechFlow",
        amount=1000.0,
        justification="test",
        urgency=Urgency.ROUTINE,
        created_at=datetime(2026, 4, 30, 12, 0, 0),
        updated_at=datetime(2026, 4, 30, 12, 0, 0),
    )


def test_session_id_is_unique_per_call():
    req = _make_request()
    with patch("src.agent.pipeline.run_evaluator", return_value=_fake_assessment(req.id)):
        a, _ = process_request(None, req)
        b, _ = process_request(None, req)
    assert a.session_id != b.session_id
    assert a.request_id == b.request_id == "PR-001"


def test_assessment_is_returned_unchanged():
    req = _make_request()
    fake = _fake_assessment(req.id)
    with patch("src.agent.pipeline.run_evaluator", return_value=fake):
        record, _span_id = process_request(None, req)
    assert record.assessment is fake
    assert record.review is None


def test_returns_root_span_id_when_tracing_active():
    """The pipeline's CHAIN root span is recording (the test conftest
    installs a TracerProvider) so `process_request` returns a 16-char
    hex span id."""
    req = _make_request("PR-007")
    with patch("src.agent.pipeline.run_evaluator", return_value=_fake_assessment(req.id)):
        record, span_id = process_request(None, req)

    assert record.request_id == "PR-007"
    assert span_id is not None
    assert len(span_id) == 16  # 8-byte span_id formatted as hex
    assert int(span_id, 16) != 0  # not the all-zero invalid context


def test_using_attributes_called_with_request_id_as_session():
    """The pipeline must open `using_attributes(session_id=request.id)` around
    the evaluator call so LangChainInstrumentor can tag every child span."""
    req = _make_request("PR-042")

    captured: dict = {}

    @contextmanager
    def fake_using_attributes(**kwargs):
        captured.update(kwargs)
        yield

    with patch("src.agent.pipeline.using_attributes", fake_using_attributes), \
         patch("src.agent.pipeline.run_evaluator", return_value=_fake_assessment(req.id)):
        process_request(None, req)

    assert captured == {"session_id": "PR-042"}


def test_override_is_forwarded_to_evaluator():
    """When `override` is passed, process_request must thread it into run_evaluator."""
    req = _make_request("PR-005")
    override = HumanOverride(decision=ReviewerDecision.REJECT, reasoning="vendor SLA")

    captured: dict = {}

    def fake_eval(conn, request, model="gpt-4o-mini", override=None):
        captured["override"] = override
        return _fake_assessment(request.id)

    with patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval):
        process_request(None, req, override=override)

    assert captured["override"] is override


def test_using_attributes_wraps_evaluator_call():
    """using_attributes must be entered before run_evaluator and exited after."""
    req = _make_request("PR-001")
    order: list[str] = []

    @contextmanager
    def fake_using_attributes(**kwargs):
        order.append("enter")
        yield
        order.append("exit")

    def fake_eval(conn, request, model="gpt-4o-mini", override=None):
        order.append("evaluator")
        return _fake_assessment(request.id)

    with patch("src.agent.pipeline.using_attributes", fake_using_attributes), \
         patch("src.agent.pipeline.run_evaluator", side_effect=fake_eval):
        process_request(None, req)

    assert order == ["enter", "evaluator", "exit"]
