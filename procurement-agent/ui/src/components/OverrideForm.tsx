"use client";

/**
 * Inline reviewer-decision form attached to an unreviewed assessment.
 *
 * Two action buttons (Approve / Reject), a required reasoning textarea,
 * and a required reviewer-name input. Submitting POSTs to
 * `/api/requests/{id}/override`, which re-runs the agent with the
 * reviewer's input as additional context and persists a `ReviewDecision`
 * against the new assessment. The whole round-trip shows up in Arize as
 * a traced agent run.
 *
 * The reviewer's name is persisted to `localStorage` so they only have
 * to type it once per browser. There's no auth in the demo — this is
 * just a self-attestation.
 */

import { useEffect, useState } from "react";
import { overrideRequest } from "@/lib/api";
import type { EvaluatorAssessment } from "@/lib/types";

interface Props {
  assessment: EvaluatorAssessment;
  onSubmitted: () => void;
}

const REVIEWER_NAME_STORAGE_KEY = "procurement-ui:reviewer-name";

export default function OverrideForm({ assessment, onSubmitted }: Props) {
  const [reasoning, setReasoning] = useState("");
  const [reviewerName, setReviewerName] = useState("");
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Hydrate the reviewer name from localStorage on mount so they don't
  // retype it for every override.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(REVIEWER_NAME_STORAGE_KEY);
      if (saved) setReviewerName(saved);
    } catch {
      // localStorage may be unavailable (private mode etc.) — proceed without.
    }
  }, []);

  async function submit(decision: "approve" | "reject") {
    if (!reasoning.trim() || !reviewerName.trim()) return;
    setSubmitting(decision);
    setError(null);
    try {
      const trimmedName = reviewerName.trim();
      try {
        window.localStorage.setItem(REVIEWER_NAME_STORAGE_KEY, trimmedName);
      } catch {
        // ignore storage failures
      }
      await overrideRequest(assessment.request_id, {
        decision,
        reasoning: reasoning.trim(),
        reviewer_name: trimmedName,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setSubmitting(null);
    }
  }

  const canSubmit =
    reasoning.trim().length > 0 &&
    reviewerName.trim().length > 0 &&
    submitting === null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider">
          Override Decision
        </span>
      </div>

      <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-1.5">
        Your name
      </label>
      <input
        value={reviewerName}
        onChange={(e) => setReviewerName(e.target.value)}
        placeholder="e.g. Vera Fye"
        disabled={submitting !== null}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-light)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-ring)] disabled:opacity-60 mb-3"
      />

      <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-1.5">
        Reasoning
      </label>
      <textarea
        value={reasoning}
        onChange={(e) => setReasoning(e.target.value)}
        placeholder="Why are you overriding? Cite specifics — vendor history, precedent, department context..."
        rows={3}
        disabled={submitting !== null}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-light)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-ring)] disabled:opacity-60"
      />

      {error && (
        <p className="text-red-700 text-xs mt-2 font-medium">{error}</p>
      )}

      <div className="flex gap-2 mt-3">
        <button
          type="button"
          onClick={() => submit("approve")}
          disabled={!canSubmit}
          className="flex-1 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting === "approve" ? "Submitting..." : "Approve"}
        </button>
        <button
          type="button"
          onClick={() => submit("reject")}
          disabled={!canSubmit}
          className="flex-1 py-2 text-sm font-semibold rounded-lg bg-red-600 text-white shadow-xs hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting === "reject" ? "Submitting..." : "Reject"}
        </button>
      </div>

      <p className="text-xs text-[var(--muted)] mt-2">
        Your name and reasoning are required and recorded with the review.
      </p>
    </div>
  );
}
