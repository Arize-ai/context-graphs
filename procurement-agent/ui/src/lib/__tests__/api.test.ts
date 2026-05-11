/**
 * Tests for `src/lib/api.ts`. Uses a mocked global `fetch` so the suite runs
 * without a backend. The smoke test (`smoke.test.ts`) confirms Vitest is wired
 * up; this file covers actual contract: URLs hit, payloads sent, errors thrown.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  attachReview,
  createRequest,
  fetchAssessments,
  fetchDepartments,
  fetchPolicies,
  fetchRequests,
  fetchVendors,
  overrideRequest,
  processRequest,
} from "../api";
import type { PurchaseRequestCreate, ReviewDecision } from "../types";

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  } as Response);
}

const origFetch = globalThis.fetch;

beforeEach(() => {
  delete (process.env as Record<string, string | undefined>).NEXT_PUBLIC_API_URL;
});

afterEach(() => {
  globalThis.fetch = origFetch;
  vi.restoreAllMocks();
});

describe("api base URL", () => {
  it("defaults to http://localhost:8000 when env unset", async () => {
    const fetchMock = mockFetch([]);
    globalThis.fetch = fetchMock;
    await fetchRequests();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/requests");
  });
});

describe("fetchRequests", () => {
  it("returns parsed JSON on 200", async () => {
    globalThis.fetch = mockFetch([{ id: "PR-001" }]);
    const result = await fetchRequests();
    expect(result).toEqual([{ id: "PR-001" }]);
  });

  it("throws on non-2xx", async () => {
    globalThis.fetch = mockFetch("error", false, 500);
    await expect(fetchRequests()).rejects.toThrow(/Failed to fetch requests: 500/);
  });
});

describe("createRequest", () => {
  it("POSTs JSON body and parses response", async () => {
    const fetchMock = mockFetch({ id: "PR-031" });
    globalThis.fetch = fetchMock;
    const body: PurchaseRequestCreate = {
      requester: "Test",
      department: "Engineering",
      item: "Laptop",
      vendor: "TechFlow",
      amount: 1500,
      justification: "Replacement",
      urgency: "routine",
    };
    const result = await createRequest(body);
    expect(result).toEqual({ id: "PR-031" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/requests");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it("includes server detail in error message on failure", async () => {
    globalThis.fetch = mockFetch("requester required", false, 422);
    await expect(
      createRequest({} as PurchaseRequestCreate),
    ).rejects.toThrow(/requester required/);
  });
});

describe("fetchDepartments / fetchVendors / fetchPolicies", () => {
  it("hit the correct GET endpoints", async () => {
    const fetchMock = mockFetch([]);
    globalThis.fetch = fetchMock;
    await fetchDepartments();
    await fetchVendors();
    await fetchPolicies();
    const urls = fetchMock.mock.calls.map((c) => c[0]);
    expect(urls).toEqual([
      "http://localhost:8000/api/departments",
      "http://localhost:8000/api/vendors",
      "http://localhost:8000/api/policies",
    ]);
  });
});

describe("processRequest", () => {
  it("POSTs to /api/requests/:id/process", async () => {
    const fetchMock = mockFetch({ request_id: "PR-001", session_id: "x" });
    globalThis.fetch = fetchMock;
    await processRequest("PR-001");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/requests/PR-001/process");
    expect(init.method).toBe("POST");
  });
});

describe("fetchAssessments", () => {
  it("hits /api/requests/:id/assessments", async () => {
    const fetchMock = mockFetch([]);
    globalThis.fetch = fetchMock;
    await fetchAssessments("PR-007");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/requests/PR-007/assessments",
    );
  });
});

describe("overrideRequest", () => {
  it("POSTs to /api/requests/:id/override with the override body", async () => {
    const fetchMock = mockFetch({ request_id: "PR-001" });
    globalThis.fetch = fetchMock;
    await overrideRequest("PR-001", {
      decision: "reject",
      reasoning: "vendor SLA concerns",
      reviewer_name: "Vera Fye",
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/requests/PR-001/override");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      decision: "reject",
      reasoning: "vendor SLA concerns",
      reviewer_name: "Vera Fye",
    });
  });
});

describe("attachReview", () => {
  it("POSTs the review to /api/assessments/:session_id/review", async () => {
    const fetchMock = mockFetch({ request_id: "PR-001" });
    globalThis.fetch = fetchMock;
    const review: ReviewDecision = {
      request_id: "PR-001",
      agent_recommendation: "approve",
      reviewer_decision: "reject",
      reviewer_name: "Vera Fye",
      override: true,
      reasoning: "vendor history",
      precedent_applied: "DT-0007",
      conditions: "",
      confidence: "high",
    };
    await attachReview("session-xyz", review);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/assessments/session-xyz/review");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(review);
  });
});
