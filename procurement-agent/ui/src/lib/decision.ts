/**
 * Helpers for deriving the "final decision" of a purchase request.
 *
 * A request's outcome is sourced (in order of authority):
 *   1. The latest assessment's reviewer override, if a human review is attached.
 *   2. Otherwise, the latest assessment's agent recommendation.
 *   3. Otherwise (no assessments yet) → null.
 *
 * "Latest" means highest `created_at` on the assessment record. The
 * sidebar uses this to split completed requests into Approved / Rejected
 * tabs, and the detail view uses it to render a clear status banner.
 */

import type { AssessmentRecord, Recommendation } from "./types";

export type FinalDecision = Recommendation | null;

/** Pick the most recent assessment for a given request id. */
export function latestAssessment(
  requestId: string,
  assessments: AssessmentRecord[],
): AssessmentRecord | null {
  let latest: AssessmentRecord | null = null;
  for (const a of assessments) {
    if (a.request_id !== requestId) continue;
    if (!latest || a.created_at > latest.created_at) latest = a;
  }
  return latest;
}

/** Derive the final decision from a single assessment record. */
export function decisionOf(record: AssessmentRecord | null): FinalDecision {
  if (!record) return null;
  if (record.review) return record.review.reviewer_decision as Recommendation;
  return record.assessment.recommendation;
}

/** Derive the final decision for a request given the full assessments list. */
export function decisionForRequest(
  requestId: string,
  assessments: AssessmentRecord[],
): FinalDecision {
  return decisionOf(latestAssessment(requestId, assessments));
}
