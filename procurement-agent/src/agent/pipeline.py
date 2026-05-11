"""Procurement evaluator pipeline — runs the LangChain agent against a request.

This module generates the per-assessment `session_id` used to correlate the
agent's output with any later human review. Reviews via the reviewer CLI
are submitted through `POST /api/requests/{id}/override` (which re-runs the
agent with the reviewer's input as context). Direct attach via
`POST /api/assessments/{session_id}/review` exists for any consumer that
wants to record a review without producing a fresh agent run.

Each call wraps the agent run in an explicit OpenInference CHAIN root
span so the override endpoint has a known `span_id` to attach the
human-review annotation to. The LangGraph spans the LangChain
instrumentor produces become children of this root.
"""

import sqlite3
import uuid

from opentelemetry import trace
from openinference.instrumentation import using_attributes

from src.agent.evaluator import run_evaluator
from src.models import AssessmentRecord, HumanOverride, PurchaseRequest


def process_request(
    conn: sqlite3.Connection,
    request: PurchaseRequest,
    model: str = "gpt-4o-mini",
    override: HumanOverride | None = None,
) -> tuple[AssessmentRecord, str | None]:
    """Run the evaluator on a purchase request and return its assessment.

    Spans produced inside this call carry `session.id = request.id` (set
    via `using_attributes`) so every run against the same purchase
    request groups into one Arize session.

    Returns a `(record, root_span_id)` tuple. `root_span_id` is the hex
    span-id of the wrapper CHAIN span — used by the override endpoint to
    attach a human-review annotation. It's `None` when tracing isn't set
    up (e.g. unit tests with ARIZE creds cleared) or when the active
    tracer returns a non-recording span.

    When `override` is provided, the reviewer's decision and reasoning
    are threaded into the agent prompt so the override appears in the
    trace and the agent produces a structured assessment that
    incorporates it.
    """
    session_id = str(uuid.uuid4())
    tracer = trace.get_tracer("procurement-agent")
    span_name = "override.run" if override else "process.run"

    root_span_id: str | None = None
    with using_attributes(session_id=request.id):
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("openinference.span.kind", "CHAIN")
            span.set_attribute("input.value", request.model_dump_json())
            assessment = run_evaluator(conn, request, model=model, override=override)
            span.set_attribute("output.value", assessment.model_dump_json())
            ctx = span.get_span_context()
            if ctx and ctx.is_valid and span.is_recording():
                root_span_id = format(ctx.span_id, "016x")

    record = AssessmentRecord(
        request_id=request.id,
        session_id=session_id,
        assessment=assessment,
    )
    return record, root_span_id
