"""FastAPI application exposing the procurement agent.

Defines the HTTP surface used by the UI and reviewer CLI: CRUD over purchase
requests + reference data, the evaluator entry point at
`POST /api/requests/{id}/process`, and the human-review attach endpoint at
`POST /api/assessments/{session_id}/review`. Importing this module
transitively imports `src.instrumentation`, which must run before any
LangChain or Anthropic module is imported so the OpenInference instrumentors
can monkey-patch them on load.
"""

import src.instrumentation  # noqa: F401  — must run before LangChain / Anthropic imports

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.agent.pipeline import process_request
from src.database import (
    get_all_assessments,
    get_all_departments,
    get_all_policies,
    get_all_purchase_requests,
    get_all_vendors,
    get_assessment_by_session,
    get_assessments_for_request,
    get_connection,
    get_latest_assessment,
    get_purchase_request,
    get_unreviewed_assessments,
    init_schema,
    insert_assessment,
    insert_purchase_request,
    insert_review,
    next_request_id,
    update_request_status,
)
from src.models import (
    AssessmentRecord,
    Department,
    HumanOverride,
    Policy,
    PurchaseRequest,
    PurchaseRequestCreate,
    Recommendation,
    RequestStatus,
    ReviewDecision,
    Vendor,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    init_schema(conn)
    conn.close()
    yield


app = FastAPI(title="Procurement Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/departments", response_model=list[Department])
def list_departments() -> list[Department]:
    conn = get_connection()
    try:
        return get_all_departments(conn)
    finally:
        conn.close()


@app.get("/api/vendors", response_model=list[Vendor])
def list_vendors() -> list[Vendor]:
    conn = get_connection()
    try:
        return get_all_vendors(conn)
    finally:
        conn.close()


@app.get("/api/policies", response_model=list[Policy])
def list_policies() -> list[Policy]:
    conn = get_connection()
    try:
        return get_all_policies(conn)
    finally:
        conn.close()


@app.get("/api/requests", response_model=list[PurchaseRequest])
def list_requests() -> list[PurchaseRequest]:
    conn = get_connection()
    try:
        return get_all_purchase_requests(conn)
    finally:
        conn.close()


@app.post("/api/requests", response_model=PurchaseRequest, status_code=201)
def create_request(body: PurchaseRequestCreate) -> PurchaseRequest:
    """Create a purchase request and immediately run the agent on it.

    The agent's assessment is persisted as part of this call. On agent
    failure the request is left in PENDING status (no assessment) and a
    500 is returned — the client can retry processing via
    `POST /api/requests/{id}/process`.
    """
    conn = get_connection()
    try:
        # Serialize the id-assignment + insert. With WAL mode, SQLite allows
        # one writer at a time; BEGIN IMMEDIATE acquires the write lock up
        # front so two concurrent creates can't both compute the same
        # `next_request_id` before either has committed.
        conn.execute("BEGIN IMMEDIATE")
        req = PurchaseRequest(
            id=next_request_id(conn),
            status=RequestStatus.PROCESSING,
            **body.model_dump(),
        )
        insert_purchase_request(conn, req)
        conn.commit()

        # Lock released. Run the agent without holding the write lock so
        # other creates can proceed in parallel.
        try:
            record, span_id = process_request(conn, req)
            record.span_id = span_id
            insert_assessment(conn, record)
            update_request_status(conn, req.id, RequestStatus.COMPLETED)
            conn.commit()
        except Exception:
            conn.rollback()
            update_request_status(conn, req.id, RequestStatus.PENDING)
            conn.commit()
            raise

        return req.model_copy(update={"status": RequestStatus.COMPLETED})
    finally:
        conn.close()


@app.get("/api/requests/{request_id}", response_model=PurchaseRequest)
def get_request(request_id: str) -> PurchaseRequest:
    conn = get_connection()
    try:
        req = get_purchase_request(conn, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        return req
    finally:
        conn.close()


@app.post("/api/requests/{request_id}/process", response_model=AssessmentRecord)
def process_purchase_request(request_id: str) -> AssessmentRecord:
    """Run the evaluator agent on a request and store its assessment.

    Does NOT produce a human review — reviews are submitted separately by
    external clients via `POST /api/assessments/{session_id}/review`,
    simulating human feedback arriving after the agent has run.
    """
    conn = get_connection()
    try:
        req = get_purchase_request(conn, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

        update_request_status(conn, request_id, RequestStatus.PROCESSING)
        conn.commit()

        try:
            record, span_id = process_request(conn, req)
            record.span_id = span_id
            insert_assessment(conn, record)
            update_request_status(conn, request_id, RequestStatus.COMPLETED)
            conn.commit()
        except Exception:
            # Agent or persistence failed after PROCESSING was committed.
            # Roll back uncommitted DB writes (assessment insert, COMPLETED
            # status), then explicitly reset status to PENDING so the request
            # isn't stuck mid-flight from a client's view.
            conn.rollback()
            update_request_status(conn, request_id, RequestStatus.PENDING)
            conn.commit()
            raise

        return record
    finally:
        conn.close()


@app.post("/api/requests/{request_id}/override", response_model=AssessmentRecord)
def override_purchase_request(request_id: str, body: HumanOverride) -> AssessmentRecord:
    """Re-run the evaluator with a human override applied.

    The reviewer's decision and reasoning are passed to the agent as
    additional context (visible in Arize traces). The agent produces a new
    structured assessment that aligns with the override; the override
    itself is then attached as a `ReviewDecision` against the new
    assessment so the new record carries both the agent output and the
    human signal that produced it.

    The previous assessment (if any) is left untouched. The trace's
    `session.id` is the request id, so the override run groups with prior
    runs in the same Arize session.
    """
    conn = get_connection()
    try:
        req = get_purchase_request(conn, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

        prior = get_latest_assessment(conn, request_id)

        try:
            record, root_span_id = process_request(conn, req, override=body)
            record.span_id = root_span_id
            insert_assessment(conn, record)

            prior_recommendation = (
                prior.assessment.recommendation if prior else record.assessment.recommendation
            )
            review = ReviewDecision(
                request_id=request_id,
                agent_recommendation=prior_recommendation,
                reviewer_decision=body.decision,
                reviewer_name=body.reviewer_name,
                override=Recommendation(body.decision.value) != prior_recommendation,
                reasoning=body.reasoning,
                precedent_applied=body.precedent_applied,
                conditions=body.conditions,
                confidence=body.confidence,
            )
            insert_review(conn, record.session_id, review)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        # Push the human-review annotation onto the root span of this
        # override run. Best-effort: failures are logged but never
        # surface — the ReviewDecision row above is the durable record
        # of human intent.
        if root_span_id:
            try:
                from src.annotations import apply_override_annotation

                apply_override_annotation(root_span_id, body)
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning(
                    "annotation push failed for span %s: %s", root_span_id, exc
                )

        return get_assessment_by_session(conn, record.session_id)
    finally:
        conn.close()


@app.get("/api/requests/{request_id}/assessments", response_model=list[AssessmentRecord])
def list_assessments_for_request(request_id: str) -> list[AssessmentRecord]:
    """Get all assessments for a request, newest first, with reviews joined when present."""
    conn = get_connection()
    try:
        req = get_purchase_request(conn, request_id)
        if req is None:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        return get_assessments_for_request(conn, request_id)
    finally:
        conn.close()


@app.get("/api/assessments", response_model=list[AssessmentRecord])
def list_all_assessments(unreviewed: bool = False) -> list[AssessmentRecord]:
    """List assessments across all requests.

    Pass `unreviewed=true` to filter to assessments that don't yet have a human
    review attached. External clients use this endpoint to find work to do.
    """
    conn = get_connection()
    try:
        if unreviewed:
            return get_unreviewed_assessments(conn)
        return get_all_assessments(conn)
    finally:
        conn.close()


@app.post("/api/assessments/{session_id}/review", response_model=AssessmentRecord)
def attach_review(session_id: str, review: ReviewDecision) -> AssessmentRecord:
    """Attach a human review to an existing assessment session.

    Used by external clients to record human feedback after the agent has
    already produced its assessment. Returns the assessment with the review joined in.
    """
    conn = get_connection()
    try:
        record = get_assessment_by_session(conn, session_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=f"No assessment found for session {session_id}"
            )
        if record.review is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Session {session_id} already has a review attached",
            )
        insert_review(conn, session_id, review)
        conn.commit()
        return get_assessment_by_session(conn, session_id)
    finally:
        conn.close()
