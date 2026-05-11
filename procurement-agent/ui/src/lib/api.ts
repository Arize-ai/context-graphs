/**
 * Typed fetch wrapper around the procurement-agent HTTP API.
 *
 * Base URL comes from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
 * Each function returns the parsed JSON on success and throws an `Error` with
 * the response body or status on failure — callers surface that to the user.
 */

import type {
  AssessmentRecord,
  Department,
  Policy,
  PurchaseRequest,
  PurchaseRequestCreate,
  ReviewDecision,
  Vendor,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchRequests(): Promise<PurchaseRequest[]> {
  const res = await fetch(`${API_BASE}/api/requests`);
  if (!res.ok) {
    throw new Error(`Failed to fetch requests: ${res.status}`);
  }
  return res.json();
}

export async function createRequest(data: PurchaseRequestCreate): Promise<PurchaseRequest> {
  const res = await fetch(`${API_BASE}/api/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to create request: ${detail}`);
  }
  return res.json();
}

export async function fetchDepartments(): Promise<Department[]> {
  const res = await fetch(`${API_BASE}/api/departments`);
  if (!res.ok) {
    throw new Error(`Failed to fetch departments: ${res.status}`);
  }
  return res.json();
}

export async function fetchVendors(): Promise<Vendor[]> {
  const res = await fetch(`${API_BASE}/api/vendors`);
  if (!res.ok) {
    throw new Error(`Failed to fetch vendors: ${res.status}`);
  }
  return res.json();
}

export async function fetchPolicies(): Promise<Policy[]> {
  const res = await fetch(`${API_BASE}/api/policies`);
  if (!res.ok) {
    throw new Error(`Failed to fetch policies: ${res.status}`);
  }
  return res.json();
}

export async function processRequest(requestId: string): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/api/requests/${requestId}/process`, {
    method: "POST",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to process request: ${detail}`);
  }
  return res.json();
}

export async function fetchAssessments(requestId: string): Promise<AssessmentRecord[]> {
  const res = await fetch(`${API_BASE}/api/requests/${requestId}/assessments`);
  if (!res.ok) {
    throw new Error(`Failed to fetch assessments: ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch every assessment in the store. Used by the UI to derive each
 * request's final decision (approve / reject / flag-for-review) for
 * sidebar filtering — too many requests to fetch per-request, so we pull
 * the whole list once and join client-side.
 */
export async function fetchAllAssessments(): Promise<AssessmentRecord[]> {
  const res = await fetch(`${API_BASE}/api/assessments`);
  if (!res.ok) {
    throw new Error(`Failed to fetch all assessments: ${res.status}`);
  }
  return res.json();
}

export async function attachReview(
  sessionId: string,
  review: ReviewDecision,
): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/api/assessments/${sessionId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(review),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to attach review: ${detail}`);
  }
  return res.json();
}

/**
 * Override a request via the agent. Posts the reviewer's decision +
 * reasoning + name to `/api/requests/{id}/override`, which re-runs the
 * evaluator with the override as context and returns the new assessment
 * with the review already attached. Use this from the UI's
 * `OverrideForm` so the override flows through Arize as a traced agent
 * run. The UI restricts decision to `"approve" | "reject"` — the
 * underlying endpoint accepts `"flag-for-review"` too but a human review
 * should be a final call.
 */
export async function overrideRequest(
  requestId: string,
  override: {
    decision: "approve" | "reject";
    reasoning: string;
    reviewer_name: string;
  },
): Promise<AssessmentRecord> {
  const res = await fetch(`${API_BASE}/api/requests/${requestId}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(override),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to override: ${detail}`);
  }
  return res.json();
}
