"use client";

/**
 * Detail pane for a selected purchase request.
 *
 * Shows the request's metadata, a "Run agent" trigger that POSTs to
 * `/api/requests/{id}/process`, and a timeline of past assessments. The
 * latest assessment without a review renders an inline `OverrideForm` so
 * the human reviewer can attach a decision in-place.
 */

import { useEffect, useState } from "react";
import { fetchAssessments, processRequest } from "@/lib/api";
import { decisionOf, type FinalDecision } from "@/lib/decision";
import type { AssessmentRecord, PurchaseRequest } from "@/lib/types";
import OverrideForm from "./OverrideForm";

interface Props {
  request: PurchaseRequest;
  onRequestUpdated: () => void;
}

const urgencyConfig: Record<string, { bg: string; text: string; label: string }> = {
  routine: { bg: "bg-slate-100", text: "text-slate-700", label: "Routine" },
  urgent: { bg: "bg-amber-100", text: "text-amber-800", label: "Urgent" },
  emergency: { bg: "bg-red-100", text: "text-red-800", label: "Emergency" },
};

const statusConfig: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  pending: { bg: "bg-sky-100", text: "text-sky-800", dot: "bg-sky-500", label: "Pending" },
  processing: { bg: "bg-amber-100", text: "text-amber-800", dot: "bg-amber-500", label: "Processing" },
  completed: { bg: "bg-emerald-100", text: "text-emerald-800", dot: "bg-emerald-500", label: "Completed" },
};

const decisionColors: Record<string, { bg: string; text: string }> = {
  approve: { bg: "bg-emerald-100", text: "text-emerald-800" },
  reject: { bg: "bg-red-100", text: "text-red-800" },
  "flag-for-review": { bg: "bg-amber-100", text: "text-amber-800" },
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatCurrency(amount: number): string {
  const isNegative = amount < 0;
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(amount));
  return isNegative ? `(${formatted})` : formatted;
}

export default function RequestDetail({ request, onRequestUpdated }: Props) {
  const [assessments, setAssessments] = useState<AssessmentRecord[]>([]);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAssessments(request.id).then(setAssessments).catch(() => {});
  }, [request.id, request.updated_at]);

  async function handleProcess() {
    setProcessing(true);
    setError(null);
    try {
      const record = await processRequest(request.id);
      setAssessments((prev) => [record, ...prev]);
      onRequestUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed");
    } finally {
      setProcessing(false);
    }
  }

  async function refetchAssessments() {
    try {
      const updated = await fetchAssessments(request.id);
      setAssessments(updated);
    } catch {
      // ignore — keep the current view rather than blanking it
    }
  }

  const urgency = urgencyConfig[request.urgency];
  const status = statusConfig[request.status];
  const isPending = request.status === "pending";
  const latestUnreviewed = assessments.find((r) => r.review === null) ?? null;

  // Latest assessment by created_at — drives the prominent status banner.
  const latestAssessment = assessments.length > 0
    ? assessments.reduce((a, b) => (a.created_at > b.created_at ? a : b))
    : null;
  const finalDecision = decisionOf(latestAssessment);
  const reviewerName = latestAssessment?.review?.reviewer_name ?? null;
  const decisionBySource: "reviewer" | "agent" | null = latestAssessment
    ? latestAssessment.review
      ? "reviewer"
      : "agent"
    : null;

  return (
    <div className="max-w-3xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-mono font-semibold text-[var(--foreground-soft)] bg-[var(--surface-muted)] border border-[var(--border)] px-2 py-0.5 rounded-md">
            {request.id}
          </span>
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold ${status.bg} ${status.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
            {status.label}
          </span>
          <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${urgency.bg} ${urgency.text}`}>
            {urgency.label}
          </span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight leading-snug text-[var(--foreground)]">
              {request.item}
            </h2>
            <p className="text-[var(--muted)] text-sm mt-1">
              Requested by <span className="font-medium text-[var(--foreground-soft)]">{request.requester}</span>
            </p>
          </div>
          <button
            onClick={handleProcess}
            disabled={processing}
            className={`flex-shrink-0 inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg transition-all disabled:opacity-50 ${
              isPending
                ? "bg-[var(--accent)] text-white shadow-sm hover:bg-[var(--accent-hover)] hover:shadow-md"
                : "border border-[var(--accent)] text-[var(--accent-active)] bg-[var(--surface)] hover:bg-[var(--accent-light)]"
            }`}
          >
            {!processing && !isPending && (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            )}
            {processing
              ? "Processing..."
              : isPending
                ? "Process Request"
                : "Re-assess"}
          </button>
        </div>
      </div>

      {/* Decision banner — final outcome of this request */}
      <DecisionBanner
        decision={finalDecision}
        source={decisionBySource}
        reviewerName={reviewerName}
      />

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 mb-6">
          <p className="text-red-800 text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Info cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <InfoCard label="Amount" value={formatCurrency(request.amount)} mono />
        <InfoCard label="Department" value={request.department} />
        <InfoCard label="Vendor" value={request.vendor} />
        <InfoCard label="Created" value={formatDate(request.created_at)} />
        <InfoCard label="Last Updated" value={formatDate(request.updated_at)} />
      </div>

      {/* Justification */}
      <div className="mb-8">
        <h3 className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-2">
          Business Justification
        </h3>
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-xs">
          <p className="text-sm leading-relaxed text-[var(--foreground-soft)]">
            {request.justification}
          </p>
        </div>
      </div>

      {/* Override Decision — only when there's a latest unreviewed assessment */}
      {latestUnreviewed && (
        <div className="mb-8">
          <h3 className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
            Override Decision
          </h3>
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-xs">
            <OverrideForm
              assessment={latestUnreviewed.assessment}
              onSubmitted={refetchAssessments}
            />
          </div>
        </div>
      )}

      {/* Decision Timeline (read-only) */}
      <div>
        <h3 className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
          Decision Timeline
          {assessments.length > 0 && (
            <span className="ml-2 text-[var(--muted)] normal-case font-medium">
              · {assessments.length} assessment{assessments.length !== 1 ? "s" : ""}
            </span>
          )}
        </h3>

        {assessments.length === 0 && !processing ? (
          <div className="border border-dashed border-[var(--border-strong)] rounded-xl p-6 text-center bg-[var(--surface-muted)]">
            <p className="text-sm text-[var(--muted)]">
              {isPending
                ? "Click \"Process Request\" to run the agent"
                : "No assessments yet"}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {assessments.map((record, idx) => (
              <AssessmentCard
                key={record.session_id}
                record={record}
                isLatest={idx === 0}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AssessmentCard({
  record,
  isLatest,
}: {
  record: AssessmentRecord;
  isLatest: boolean;
}) {
  const { assessment, review } = record;
  const recColors = decisionColors[assessment.recommendation] ?? decisionColors["flag-for-review"];
  const decColors = review
    ? decisionColors[review.reviewer_decision] ?? decisionColors["flag-for-review"]
    : null;

  return (
    <div
      className={`bg-[var(--surface)] border rounded-xl overflow-hidden shadow-xs ${
        isLatest ? "border-[var(--accent)]/40 ring-1 ring-[color:var(--accent-ring)]" : "border-[var(--border)]"
      }`}
    >
      {/* Card header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--surface-muted)] border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          {isLatest && (
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-active)] bg-[var(--accent-soft)] px-2 py-0.5 rounded-md">
              Latest
            </span>
          )}
          <span className="text-xs text-[var(--muted)]">
            {formatDate(record.created_at)}
          </span>
        </div>
        {review?.override && (
          <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-800 bg-amber-100 px-2 py-0.5 rounded-md">
            Override
          </span>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Evaluator Assessment */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider">
              Agent Assessment
            </span>
            <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${recColors.bg} ${recColors.text}`}>
              {assessment.recommendation}
            </span>
            <span className="text-[11px] text-[var(--muted)]">
              {assessment.confidence} confidence
            </span>
          </div>
          <div className="text-sm space-y-1 text-[var(--foreground-soft)]">
            <p><span className="text-[var(--muted)] font-medium">Policy:</span> {assessment.policy_details}</p>
            <p><span className="text-[var(--muted)] font-medium">Budget:</span> {assessment.budget_status}</p>
            <p><span className="text-[var(--muted)] font-medium">Vendor:</span> {assessment.vendor_status}</p>
            {assessment.risk_factors.length > 0 && (
              <p><span className="text-[var(--muted)] font-medium">Risks:</span> {assessment.risk_factors.join(", ")}</p>
            )}
            <p className="text-[var(--muted)] italic mt-2">{assessment.recommendation_reasoning}</p>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-[var(--border)]" />

        {/* Reviewer Decision (or pending indicator) */}
        {review && decColors ? (
          <div>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider">
                Human Review
              </span>
              <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${decColors.bg} ${decColors.text}`}>
                {review.reviewer_decision}
              </span>
              {review.reviewer_name && (
                <span className="text-[11px] font-medium text-[var(--foreground-soft)]">
                  by {review.reviewer_name}
                </span>
              )}
              {record.reviewed_at && (
                <span className="text-[11px] text-[var(--muted)]">
                  {formatDate(record.reviewed_at)}
                </span>
              )}
            </div>
            <div className="text-sm space-y-1 text-[var(--foreground-soft)]">
              <p>{review.reasoning}</p>
              {review.precedent_applied && (
                <p><span className="text-[var(--muted)] font-medium">Precedent:</span> {review.precedent_applied}</p>
              )}
              {review.conditions && (
                <p><span className="text-[var(--muted)] font-medium">Conditions:</span> {review.conditions}</p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-[var(--muted)] italic">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Awaiting decision
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-xs">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-1.5">{label}</p>
      <p className={`text-sm font-semibold text-[var(--foreground)] ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

interface DecisionBannerProps {
  decision: FinalDecision;
  source: "reviewer" | "agent" | null;
  reviewerName: string | null;
}

/** Prominent status banner above the request detail. */
function DecisionBanner({ decision, source, reviewerName }: DecisionBannerProps) {
  const config = (() => {
    if (decision === "approve") {
      return {
        bg: "bg-emerald-50",
        border: "border-emerald-300",
        text: "text-emerald-900",
        sub: "text-emerald-700",
        iconColor: "text-emerald-600",
        label: "Approved",
        icon: (
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        ),
      };
    }
    if (decision === "reject") {
      return {
        bg: "bg-red-50",
        border: "border-red-300",
        text: "text-red-900",
        sub: "text-red-700",
        iconColor: "text-red-600",
        label: "Rejected",
        icon: (
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        ),
      };
    }
    if (decision === "flag-for-review") {
      return {
        bg: "bg-amber-50",
        border: "border-amber-300",
        text: "text-amber-900",
        sub: "text-amber-700",
        iconColor: "text-amber-600",
        label: "Flagged for review",
        icon: (
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        ),
      };
    }
    return {
      bg: "bg-slate-50",
      border: "border-slate-300",
      text: "text-slate-900",
      sub: "text-slate-700",
      iconColor: "text-slate-500",
      label: "Pending — agent has not run yet",
      icon: (
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      ),
    };
  })();

  const sourceLabel = decision && source
    ? source === "reviewer"
      ? reviewerName
        ? `by ${reviewerName}`
        : "by human reviewer"
      : "by agent"
    : null;

  return (
    <div
      role="status"
      aria-label={`Decision: ${config.label}`}
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 mb-6 shadow-xs ${config.bg} ${config.border} ${config.text}`}
    >
      <svg
        className={`w-7 h-7 flex-shrink-0 ${config.iconColor}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.75}
      >
        {config.icon}
      </svg>
      <div className="flex-1">
        <p className="text-sm font-semibold">{config.label}</p>
        {sourceLabel && (
          <p className={`text-xs ${config.sub} font-medium`}>{sourceLabel}</p>
        )}
      </div>
    </div>
  );
}
