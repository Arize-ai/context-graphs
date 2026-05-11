"""Procurement evaluator — a LangChain agent that assesses purchase requests against policy.

The agent decides which tools to call (policy / vendor / budget lookups) and
produces a structured `EvaluatorAssessment` via `create_agent`'s
`response_format`. When a `HumanOverride` is supplied, its decision and
reasoning are appended to the user message so the override flows into the
agent's input — and therefore into the Arize trace.
"""

import sqlite3

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from src.agent.tools import check_budget, check_policy, lookup_department, lookup_vendor
from src.models import EvaluatorAssessment, HumanOverride, PurchaseRequest
from src.variants import load_variant

SYSTEM_PROMPT = """You are a procurement evaluator for a mid-sized organization. You read incoming purchase requests, gather the relevant policy, vendor, and budget context using the tools available to you, and produce an objective compliance assessment.

You do NOT make the final approval decision — a human reviewer will do that. Your job is to be accurate and policy-driven.

Important guidelines:
- If the vendor is suspended or not on the approved list, flag the request as non-compliant.
- If the amount exceeds the relevant threshold, note the required approval level.
- Be specific about which policies apply and whether the request complies.
- Note any risk factors (approaching budget limits, vendor issues, etc.).
- Your recommendation should be based purely on policy compliance, not institutional knowledge or relationships.
- Always call check_policy, lookup_vendor, and check_budget before producing your assessment.

When the user message includes a HUMAN REVIEW OVERRIDE block, treat it as authoritative input from the reviewer:
- Your `recommendation` field MUST match the reviewer's decision.
- Your `recommendation_reasoning` MUST explain how the reviewer's reasoning changes the policy/risk picture vs. a baseline reading of the request.
- Still call the tools and populate `policy_compliance`, `vendor_status`, and `budget_status` accurately — the reviewer's input does not change the underlying facts, only the recommendation."""


def _build_user_message(request: PurchaseRequest, override: HumanOverride | None = None) -> str:
    base = f"""Evaluate this purchase request:

REQUEST DETAILS:
- ID: {request.id}
- Requester: {request.requester}
- Department: {request.department}
- Item: {request.item}
- Vendor: {request.vendor}
- Amount: ${request.amount:,.2f}
- Justification: {request.justification}
- Urgency: {request.urgency.value}

Steps:
1. Call check_policy with the amount and vendor to get the applicable policy and approval tier.
2. Call lookup_vendor with the vendor name to check status and notes.
3. Call check_budget with the department and amount to confirm budget headroom.
4. Synthesize the results into a structured assessment with policy_compliance, recommendation, confidence, and any risk factors.

Set request_id to "{request.id}" in your output."""

    if override is None:
        return base

    reviewer = override.reviewer_name or "an unnamed reviewer"
    override_lines = [
        f"- Reviewer: {reviewer}",
        f"- Reviewer's decision: {override.decision.value}",
        f"- Reviewer's reasoning: {override.reasoning}",
    ]
    if override.precedent_applied:
        override_lines.append(f"- Precedent applied: {override.precedent_applied}")
    if override.conditions:
        override_lines.append(f"- Conditions: {override.conditions}")
    override_lines.append(f"- Reviewer's confidence: {override.confidence.value}")

    return base + "\n\nHUMAN REVIEW OVERRIDE\n" + (
        f"{reviewer} has overridden the agent's previous recommendation:\n"
        + "\n".join(override_lines)
        + "\n\nApply the override per the system instructions: align your"
        " `recommendation` with the reviewer's decision and adjust"
        " `recommendation_reasoning` to explain how their reasoning"
        " (including any precedent or conditions) shifts the picture."
    )


def run_evaluator(
    conn: sqlite3.Connection,
    request: PurchaseRequest,
    model: str = "gpt-4o-mini",
    override: HumanOverride | None = None,
) -> EvaluatorAssessment:
    """Run the LangChain procurement evaluator and return its structured assessment.

    When `override` is provided, the reviewer's decision and reasoning are
    embedded in the user message; the system prompt instructs the agent to
    align its recommendation with the reviewer.

    The `conn` argument is kept for backward compatibility with existing callers
    but is unused — LangChain tools open their own connections via `get_connection`.
    """
    del conn  # unused; tools manage their own connections

    # Variant gating: when EXPERIMENT_VARIANT is unset, baseline behavior is
    # byte-identical to pre-variant — same tool list, same system prompt.
    variant = load_variant()
    tools = [check_policy, lookup_vendor, check_budget]
    system_prompt = SYSTEM_PROMPT
    if variant.is_active:
        tools.append(lookup_department)
        if variant.extra_context:
            system_prompt = SYSTEM_PROMPT + "\n\n" + variant.extra_context

    agent = create_agent(
        model=ChatOpenAI(model=model),
        tools=tools,
        system_prompt=system_prompt,
        response_format=EvaluatorAssessment,
    )

    result = agent.invoke({"messages": [("user", _build_user_message(request, override))]})
    structured = result.get("structured_response")
    if structured is None:
        raise RuntimeError(
            f"LangChain evaluator did not produce a structured output for {request.id}: {result}"
        )
    return structured
