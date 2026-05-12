"""Vera Fye — the human reviewer simulator.

Encodes the persona, decision rules, and output schema for the reviewer.
The institutional-knowledge content (vendor relationships, department
dynamics, seasonal context, precedents) is data, not code — it lives in
`institutional-knowledge.md` at the repo root of this app and is read at
startup. Edit that file to teach Vera something new; restart the process
to pick up the change.

The gap between Vera's decisions and the agent's recommendations is what
makes the resulting decision traces valuable.
"""

import os
from pathlib import Path

from anthropic import Anthropic

from src.models import EvaluatorAssessment, PurchaseRequest, ReviewDecision

DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "institutional-knowledge.md"


def _load_knowledge(path: Path | None = None) -> str:
    """Read the institutional-knowledge markdown file.

    Resolution order:
      1. Explicit `path` argument (used by tests).
      2. `REVIEWER_KNOWLEDGE_PATH` env var.
      3. The repo-relative default at `reviewer-agent/institutional-knowledge.md`.
    """
    resolved = path or Path(os.environ.get("REVIEWER_KNOWLEDGE_PATH", DEFAULT_KNOWLEDGE_PATH))
    if not resolved.is_file():
        raise FileNotFoundError(
            f"reviewer-agent: institutional knowledge file not found at {resolved}. "
            "Set REVIEWER_KNOWLEDGE_PATH or restore the default at "
            f"{DEFAULT_KNOWLEDGE_PATH}."
        )
    return resolved.read_text(encoding="utf-8").strip()


SYSTEM_PROMPT_TEMPLATE = """You are Vera Fye, a finance manager with years of experience at this organization. You review procurement agent assessments and make the actual approval decision.

You carry institutional knowledge that policy doesn't capture. This is critical — the gap between your decisions and policy is what creates valuable decision traces.

{knowledge}

DECISION GUIDELINES:
- Your decision MUST be either "approve" or "reject" — never "flag-for-review". You are the human reviewer; the whole point of human review is to make a final call. The agent uses "flag-for-review" to defer to you; you do not defer back to it.
- Set override=true whenever your decision differs from the agent's recommendation.

REQUIRED STRUCTURE WHEN OVERRIDING (override=true):
- reasoning: 2-4 sentences referencing specific institutional knowledge.
- precedent_applied: a SHORT snake-case tag (1-5 words, hyphens). REQUIRED — never empty, never "N/A". Use the same tag for the same precedent so the same pattern clusters across many requests. Canonical tags to reuse where they fit:
    vertex-march-outage-goodwill   — emergency pricing during the March outage
    cloudbase-cto-relationship     — CTO has a personal relationship with CloudBase's CEO
    datastream-cost-overrun        — DataStream's quotes inflate ~40% in implementation
    insight-partners-double-billed — suspended after 2024 billing dispute
    engineering-sandbag            — Engineering underestimates ~30%; treat amount as a floor
    marketing-panic-buy            — single-campaign tools that get abandoned
    customer-success-understaffed  — give CS the benefit of the doubt on urgency
    cfo-vendor-consolidation       — Q1 directive: one vendor per category
    annual-renewal-price-pushback  — renewals with >10% price increase
    security-breach-precedent      — over-budget security tools approved post-breach
  Coin a new tag for a precedent not on this list — keep it short and reusable across future requests citing the same idea.
- conditions: REQUIRED when decision is "approve" with caveats (e.g. resubmit at lower amount, time-limited approval, post-hoc review). Empty string only for clean unconditional approves and for rejections.

WHEN AGREEING (override=false):
- reasoning: 1-2 sentences naming why the agent's call is right.
- precedent_applied: empty string.
- conditions: empty string unless the agreement is conditional."""


def _build_system_prompt(knowledge: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(knowledge=knowledge)


SYSTEM_PROMPT = _build_system_prompt(_load_knowledge())


# Anthropic structured output is delivered through tool use. We declare one
# tool whose input schema is `ReviewDecision`, then force Claude to call it
# via `tool_choice`. The tool's `input` block on the response is the
# structured review.
_REVIEW_TOOL_NAME = "submit_review"
_REVIEW_TOOL = {
    "name": _REVIEW_TOOL_NAME,
    "description": (
        "Submit Vera Fye's final review decision for a procurement request. "
        "All fields are required per the system prompt's structure rules."
    ),
    "input_schema": ReviewDecision.model_json_schema(),
}


def run_reviewer(
    client: Anthropic,
    request: PurchaseRequest,
    assessment: EvaluatorAssessment,
    model: str = "claude-haiku-4-5",
) -> ReviewDecision:
    """Run Vera on an existing assessment and return her decision."""
    user_message = f"""Review this procurement assessment:

PURCHASE REQUEST:
- ID: {request.id}
- Requester: {request.requester}
- Department: {request.department}
- Item: {request.item}
- Vendor: {request.vendor}
- Amount: ${request.amount:,.2f}
- Justification: {request.justification}
- Urgency: {request.urgency.value}

EVALUATOR ASSESSMENT:
- Policy compliance: {assessment.policy_compliance.value}
- Policy details: {assessment.policy_details}
- Budget status: {assessment.budget_status}
- Vendor status: {assessment.vendor_status}
- Duplicate check: {assessment.duplicate_check}
- History notes: {assessment.history_notes}
- Recommendation: {assessment.recommendation.value}
- Reasoning: {assessment.recommendation_reasoning}
- Confidence: {assessment.confidence.value}
- Risk factors: {', '.join(assessment.risk_factors) if assessment.risk_factors else 'None'}

Make your decision as Vera Fye. Call the `submit_review` tool with your decision. If you override the agent's recommendation, explain why using your institutional knowledge."""

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[_REVIEW_TOOL],
        tool_choice={"type": "tool", "name": _REVIEW_TOOL_NAME},
    )

    tool_use = next(
        (block for block in response.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_use is None:
        raise RuntimeError(
            f"reviewer-agent: model did not call `{_REVIEW_TOOL_NAME}` for "
            f"request {request.id} (stop_reason={response.stop_reason}, "
            f"content blocks={[getattr(b, 'type', '?') for b in response.content]})"
        )

    return ReviewDecision.model_validate(tool_use.input)
