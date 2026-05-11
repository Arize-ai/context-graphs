/**
 * Domain types for the procurement UI.
 *
 * These mirror the Pydantic models in `procurement-agent/src/models.py` and
 * `procurement-reviewer/src/models.py`. Field names and enum values must
 * stay in sync across all three; the agent treats this contract as the
 * wire format for both the UI and the reviewer CLI.
 */

export type Urgency = "routine" | "urgent" | "emergency";
export type RequestStatus = "pending" | "processing" | "completed";
export type VendorStatus = "preferred" | "approved" | "suspended" | "not_listed";

export interface PurchaseRequest {
  id: string;
  requester: string;
  department: string;
  item: string;
  vendor: string;
  amount: number;
  justification: string;
  urgency: Urgency;
  status: RequestStatus;
  created_at: string;
  updated_at: string;
}

export interface PurchaseRequestCreate {
  requester: string;
  department: string;
  item: string;
  vendor: string;
  amount: number;
  justification: string;
  urgency: Urgency;
}

export interface Department {
  name: string;
  headcount: number;
  quarterly_budget: number;
}

export interface Vendor {
  name: string;
  status: VendorStatus;
  categories: string[];
  notes: string;
}

export interface Policy {
  name: string;
  description: string;
  rules: string[];
}

export type PolicyCompliance = "compliant" | "non-compliant" | "edge-case";
export type Recommendation = "approve" | "reject" | "flag-for-review";
export type ReviewerDecisionType = "approve" | "reject" | "flag-for-review";
export type Confidence = "high" | "medium" | "low";

export interface EvaluatorAssessment {
  request_id: string;
  policy_compliance: PolicyCompliance;
  policy_details: string;
  budget_status: string;
  vendor_status: string;
  duplicate_check: string;
  history_notes: string;
  recommendation: Recommendation;
  recommendation_reasoning: string;
  confidence: Confidence;
  risk_factors: string[];
}

export interface ReviewDecision {
  request_id: string;
  agent_recommendation: Recommendation;
  reviewer_decision: ReviewerDecisionType;
  reviewer_name: string;
  override: boolean;
  reasoning: string;
  precedent_applied: string;
  conditions: string;
  confidence: Confidence;
}

export interface AssessmentRecord {
  request_id: string;
  session_id: string;
  assessment: EvaluatorAssessment;
  review: ReviewDecision | null;
  created_at: string;
  reviewed_at: string | null;
}
