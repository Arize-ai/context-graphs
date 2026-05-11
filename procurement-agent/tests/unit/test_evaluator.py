"""Tests for src/agent/evaluator.run_evaluator variant gating.

The evaluator's contract is: with no `EXPERIMENT_VARIANT` set, the tools
list and system prompt passed to `create_agent` must be byte-identical
to the pre-variant baseline. With a variant active, `lookup_department`
joins the tool list and the variant's `extra_context` is appended to the
system prompt.

These tests stub out `create_agent` so the LLM is never invoked.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.agent import evaluator as ev_mod
from src.models import (
    Confidence,
    EvaluatorAssessment,
    PolicyCompliance,
    PurchaseRequest,
    Recommendation,
    Urgency,
)
from src.variants import VARIANT_ENV, Variant


def _fake_assessment() -> EvaluatorAssessment:
    return EvaluatorAssessment(
        request_id="PR-001",
        policy_compliance=PolicyCompliance.COMPLIANT,
        recommendation=Recommendation.APPROVE,
        confidence=Confidence.HIGH,
    )


def _make_request() -> PurchaseRequest:
    return PurchaseRequest(
        id="PR-001",
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


@pytest.fixture
def stub_create_agent(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace `create_agent` and `ChatOpenAI` so no LLM is invoked.

    Returns a dict that captures the kwargs `create_agent` was called with.
    """
    captured: dict = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        agent = MagicMock()
        agent.invoke.return_value = {"structured_response": _fake_assessment()}
        return agent

    monkeypatch.setattr(ev_mod, "create_agent", fake_create_agent)
    monkeypatch.setattr(ev_mod, "ChatOpenAI", MagicMock)
    return captured


def test_baseline_tool_list_excludes_lookup_department(
    monkeypatch: pytest.MonkeyPatch, stub_create_agent: dict
) -> None:
    monkeypatch.delenv(VARIANT_ENV, raising=False)
    monkeypatch.setattr(ev_mod, "load_variant", lambda: Variant())

    ev_mod.run_evaluator(None, _make_request())

    tool_names = [t.name for t in stub_create_agent["tools"]]
    assert tool_names == ["check_policy", "lookup_vendor", "check_budget"]


def test_baseline_system_prompt_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, stub_create_agent: dict
) -> None:
    monkeypatch.delenv(VARIANT_ENV, raising=False)
    monkeypatch.setattr(ev_mod, "load_variant", lambda: Variant())

    ev_mod.run_evaluator(None, _make_request())

    assert stub_create_agent["system_prompt"] == ev_mod.SYSTEM_PROMPT


def test_active_variant_appends_lookup_department(
    monkeypatch: pytest.MonkeyPatch, stub_create_agent: dict
) -> None:
    variant = Variant(id="cycle-1-A", extra_context="Read context graph signals.")
    monkeypatch.setattr(ev_mod, "load_variant", lambda: variant)

    ev_mod.run_evaluator(None, _make_request())

    tool_names = [t.name for t in stub_create_agent["tools"]]
    assert "lookup_department" in tool_names
    assert tool_names == [
        "check_policy",
        "lookup_vendor",
        "check_budget",
        "lookup_department",
    ]


def test_active_variant_appends_extra_context_to_prompt(
    monkeypatch: pytest.MonkeyPatch, stub_create_agent: dict
) -> None:
    variant = Variant(id="cycle-1-A", extra_context="Read context graph signals.")
    monkeypatch.setattr(ev_mod, "load_variant", lambda: variant)

    ev_mod.run_evaluator(None, _make_request())

    prompt = stub_create_agent["system_prompt"]
    assert prompt.startswith(ev_mod.SYSTEM_PROMPT)
    assert prompt.endswith("Read context graph signals.")


def test_active_variant_with_empty_extra_context_uses_baseline_prompt(
    monkeypatch: pytest.MonkeyPatch, stub_create_agent: dict
) -> None:
    """A variant that supplies no system_prompt.txt should not modify the prompt."""
    variant = Variant(id="cycle-1-B-data-only", extra_context="")
    monkeypatch.setattr(ev_mod, "load_variant", lambda: variant)

    ev_mod.run_evaluator(None, _make_request())

    assert stub_create_agent["system_prompt"] == ev_mod.SYSTEM_PROMPT
    # But lookup_department is still registered (variant is active).
    tool_names = [t.name for t in stub_create_agent["tools"]]
    assert "lookup_department" in tool_names
