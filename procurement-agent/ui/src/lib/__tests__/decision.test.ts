/**
 * Tests for `lib/decision.ts`. The page sidebar uses these helpers to
 * split requests into Pending / Approved / Rejected, so the precedence
 * matters: a human review wins over the agent's recommendation.
 */

import { describe, expect, it } from "vitest";
import {
  decisionForRequest,
  decisionOf,
  latestAssessment,
} from "../decision";
import type { AssessmentRecord } from "../types";

function makeRecord(over: Partial<AssessmentRecord> & { request_id: string; created_at: string }): AssessmentRecord {
  return {
    request_id: over.request_id,
    session_id: over.session_id ?? "s",
    assessment: over.assessment ?? {
      request_id: over.request_id,
      policy_compliance: "compliant",
      policy_details: "",
      budget_status: "",
      vendor_status: "",
      duplicate_check: "",
      history_notes: "",
      recommendation: "approve",
      recommendation_reasoning: "",
      confidence: "high",
      risk_factors: [],
    },
    review: over.review ?? null,
    created_at: over.created_at,
    reviewed_at: over.reviewed_at ?? null,
  };
}

describe("decisionOf", () => {
  it("returns null when given null", () => {
    expect(decisionOf(null)).toBe(null);
  });

  it("returns the agent recommendation when no review is attached", () => {
    const r = makeRecord({ request_id: "PR-1", created_at: "2026-04-01T00:00:00" });
    r.assessment.recommendation = "approve";
    expect(decisionOf(r)).toBe("approve");
  });

  it("prefers the reviewer's decision when one is attached", () => {
    const r = makeRecord({ request_id: "PR-1", created_at: "2026-04-01T00:00:00" });
    r.assessment.recommendation = "approve";
    r.review = {
      request_id: "PR-1",
      agent_recommendation: "approve",
      reviewer_decision: "reject",
      reviewer_name: "Vera Fye",
      override: true,
      reasoning: "vendor SLA",
      precedent_applied: "",
      conditions: "",
      confidence: "high",
    };
    expect(decisionOf(r)).toBe("reject");
  });
});

describe("latestAssessment", () => {
  it("returns null when no assessments match the request id", () => {
    expect(latestAssessment("PR-X", [])).toBe(null);
  });

  it("returns the assessment with the largest created_at for the request", () => {
    const a = makeRecord({ request_id: "PR-1", created_at: "2026-04-01T00:00:00" });
    const b = makeRecord({ request_id: "PR-1", created_at: "2026-04-02T00:00:00" });
    const c = makeRecord({ request_id: "PR-2", created_at: "2026-04-03T00:00:00" });
    expect(latestAssessment("PR-1", [a, b, c])).toBe(b);
  });
});

describe("decisionForRequest", () => {
  it("walks all assessments to derive the latest decision", () => {
    const older = makeRecord({ request_id: "PR-1", created_at: "2026-04-01T00:00:00" });
    older.assessment.recommendation = "approve";
    const newer = makeRecord({ request_id: "PR-1", created_at: "2026-04-02T00:00:00" });
    newer.assessment.recommendation = "reject";
    expect(decisionForRequest("PR-1", [older, newer])).toBe("reject");
  });

  it("returns null for requests with no assessments", () => {
    expect(decisionForRequest("PR-NEW", [])).toBe(null);
  });
});
