"""CLI entry — simulate Vera Fye's review on agent assessments.

Reviews are sent through the agent's `/api/requests/{id}/override` endpoint
so each Vera review re-runs the agent with her decision + reasoning as
input. That run is captured in Arize (the agent tags spans with
`session.id = request.id`), giving a traced record of every Vera decision.

Because the override flow creates a new assessment instead of mutating the
old one, the reviewer is idempotent: it only acts when the LATEST
assessment for a request is unreviewed. Re-running on a request Vera has
already reviewed is a no-op.

Usage:
    uv run python -m src PR-001                 # latest unreviewed assessment for one request
    uv run python -m src PR-001 PR-002 PR-005   # multiple requests
    uv run python -m src --all                  # every request whose latest assessment is unreviewed
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from openai import OpenAI

from src.api_client import AgentClient
from src.models import AssessmentRecord, HumanOverride, PurchaseRequest, ReviewDecision
from src.reviewer import run_reviewer


REVIEWER_NAME = "Vera Fye"


def _needs_review(record: AssessmentRecord) -> bool:
    """A request's latest assessment needs human review when:

    - it has no review attached yet, OR
    - it has a review whose `reviewer_decision` is `flag-for-review`. A
      human "flag-for-review" is a contradiction — the whole point of
      human review is a final call. Treat such records as still pending
      so they get a decisive decision on the next pass.
    """
    if record.review is None:
        return True
    return record.review.reviewer_decision.value == "flag-for-review"


def _to_override(review: ReviewDecision) -> HumanOverride:
    """Project Vera's full ReviewDecision down to the agent's override body."""
    return HumanOverride(
        decision=review.reviewer_decision,
        reasoning=review.reasoning,
        reviewer_name=REVIEWER_NAME,
        precedent_applied=review.precedent_applied,
        conditions=review.conditions,
        confidence=review.confidence,
    )


def _latest_per_request(records: list[AssessmentRecord]) -> dict[str, AssessmentRecord]:
    """Group assessments by request id, keeping only the newest per request."""
    latest: dict[str, AssessmentRecord] = {}
    for record in records:
        existing = latest.get(record.request_id)
        if existing is None or record.created_at > existing.created_at:
            latest[record.request_id] = record
    return latest


def _review_one(
    openai_client: OpenAI,
    agent: AgentClient,
    request: PurchaseRequest,
    record: AssessmentRecord,
    model: str,
) -> bool:
    """Generate Vera's decision and route it through /override. True on success."""
    review = run_reviewer(openai_client, request, record.assessment, model=model)
    body = _to_override(review)
    try:
        agent.override(request.id, body)
    except httpx.HTTPStatusError as exc:
        print(
            f"  ! {request.id}: agent rejected override "
            f"({exc.response.status_code}): {exc.response.text}",
            file=sys.stderr,
        )
        return False

    decision = review.reviewer_decision.value
    override_marker = " [OVERRIDE]" if review.override else ""
    print(f"  ✓ {request.id}: {decision}{override_marker}")
    return True


def _review_request(
    openai_client: OpenAI,
    agent: AgentClient,
    request_id: str,
    model: str,
) -> bool:
    request = agent.get_request(request_id)
    if request is None:
        print(f"  ! {request_id}: not found", file=sys.stderr)
        return False

    records = agent.get_assessments_for_request(request_id)
    if not records:
        print(f"  ! {request_id}: no assessment yet — run /process first", file=sys.stderr)
        return False

    # Records come back newest first; only act if the latest is unreviewed
    # or carries a non-decisive reviewer decision.
    latest = records[0]
    if not _needs_review(latest):
        print(f"  - {request_id}: latest assessment already has a final decision")
        return False

    return _review_one(openai_client, agent, request, latest, model)


def _review_all(
    openai_client: OpenAI,
    agent: AgentClient,
    model: str,
    parallel: int = 1,
) -> int:
    """Review the latest assessment for every request that needs one.

    "Needs one" = no review attached, OR a review whose decision is the
    non-decisive `flag-for-review` (see `_needs_review`).

    With `parallel > 1`, reviews run concurrently in a ThreadPoolExecutor.
    The httpx.Client and OpenAI client are both safe to share across
    threads. Output ordering will interleave but progress lines stay
    intact.
    """
    by_request = _latest_per_request(agent.get_all_assessments())
    pending = [r for r in by_request.values() if _needs_review(r)]
    if not pending:
        print("No requests with an unreviewed latest assessment.")
        return 0

    print(f"Reviewing {len(pending)} request(s) (parallel={parallel})...")

    def _process(record: AssessmentRecord) -> bool:
        request = agent.get_request(record.request_id)
        if request is None:
            print(f"  ! {record.request_id}: not found", file=sys.stderr)
            return False
        return _review_one(openai_client, agent, request, record, model)

    if parallel <= 1:
        return sum(1 for record in pending if _process(record))

    count = 0
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = [pool.submit(_process, record) for record in pending]
        for future in as_completed(futures):
            try:
                if future.result():
                    count += 1
            except Exception as e:  # noqa: BLE001 — surface and continue
                print(f"  ! worker error: {e}", file=sys.stderr)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reviewer-agent",
        description="Simulate Vera Fye's review on procurement-agent assessments.",
    )
    parser.add_argument(
        "request_ids",
        nargs="*",
        help="One or more request IDs (e.g. PR-001). Reviews each request whose latest assessment is unreviewed.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Review every request in the store whose latest assessment is unreviewed.",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini).")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Concurrent workers when running with --all (default: 1, sequential).",
    )
    args = parser.parse_args(argv)

    if not args.request_ids and not args.all:
        parser.error("Provide one or more request IDs, or pass --all.")
    if args.request_ids and args.all:
        parser.error("--all is mutually exclusive with explicit request IDs.")
    if args.parallel < 1:
        parser.error("--parallel must be >= 1")

    openai_client = OpenAI()
    with AgentClient() as agent:
        if args.all:
            _review_all(openai_client, agent, args.model, parallel=args.parallel)
        else:
            for rid in args.request_ids:
                _review_request(openai_client, agent, rid, args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
