"""HTTP client for the procurement-agent API."""

import os

import httpx

from src.models import AssessmentRecord, HumanOverride, PurchaseRequest, ReviewDecision

DEFAULT_AGENT_URL = "http://localhost:8000"


class AgentClient:
    """Thin client over the procurement-agent's HTTP API.

    The reviewer never touches the agent's database directly. It reads
    assessments and writes reviews through the same API surface any external
    consumer would use.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("PROCUREMENT_AGENT_URL", DEFAULT_AGENT_URL)).rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AgentClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def get_request(self, request_id: str) -> PurchaseRequest | None:
        resp = self._client.get(f"/api/requests/{request_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return PurchaseRequest.model_validate(resp.json())

    def get_assessments_for_request(self, request_id: str) -> list[AssessmentRecord]:
        resp = self._client.get(f"/api/requests/{request_id}/assessments")
        resp.raise_for_status()
        return [AssessmentRecord.model_validate(item) for item in resp.json()]

    def get_unreviewed_assessments(self) -> list[AssessmentRecord]:
        resp = self._client.get("/api/assessments", params={"unreviewed": "true"})
        resp.raise_for_status()
        return [AssessmentRecord.model_validate(item) for item in resp.json()]

    def get_all_assessments(self) -> list[AssessmentRecord]:
        """Every assessment in the store. Used to derive the latest-per-request
        for idempotent review runs (the override flow creates new assessments
        rather than mutating old ones, so an "unreviewed" assessment may be
        superseded by a newer reviewed one)."""
        resp = self._client.get("/api/assessments")
        resp.raise_for_status()
        return [AssessmentRecord.model_validate(item) for item in resp.json()]

    def attach_review(self, session_id: str, review: ReviewDecision) -> AssessmentRecord:
        """Legacy direct-attach path — does NOT re-run the agent and does
        NOT produce an Arize trace. The reviewer CLI prefers `override(...)`
        below; this stays around for any consumer that wants pure data
        attachment without a fresh agent run."""
        resp = self._client.post(
            f"/api/assessments/{session_id}/review",
            json=review.model_dump(mode="json"),
        )
        resp.raise_for_status()
        return AssessmentRecord.model_validate(resp.json())

    def override(self, request_id: str, body: HumanOverride) -> AssessmentRecord:
        """Send the reviewer's decision through the agent's override endpoint.

        The agent re-runs with the override embedded in its prompt — that
        run is captured in Arize, tagged with `session.id = request_id`.
        The returned `AssessmentRecord` is the new assessment with the
        review already attached.
        """
        resp = self._client.post(
            f"/api/requests/{request_id}/override",
            json=body.model_dump(mode="json"),
        )
        resp.raise_for_status()
        return AssessmentRecord.model_validate(resp.json())
