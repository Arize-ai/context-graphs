"use client";

/**
 * Top-level client component for the procurement UI.
 *
 * Owns the active tab (Flagged / Approved / Rejected / Policies / Vendors)
 * and the selected request id. Fetches the request list and the full
 * assessment list once on mount, derives each request's final decision
 * (latest review override, falling back to the agent's recommendation),
 * and filters the sidebar accordingly. The "New Request" affordance opens
 * a `SlideOver` containing `NewRequestForm` and is available from any of
 * the three request tabs — there is no Pending tab because every created
 * request is auto-processed by the agent on submit.
 */

import { useEffect, useMemo, useState } from "react";
import { fetchAllAssessments, fetchRequests } from "@/lib/api";
import { decisionForRequest, type FinalDecision } from "@/lib/decision";
import type { AssessmentRecord, PurchaseRequest } from "@/lib/types";
import RequestList from "@/components/RequestList";
import RequestDetail from "@/components/RequestDetail";
import SlideOver from "@/components/SlideOver";
import NewRequestForm from "@/components/NewRequestForm";
import TopNav, { type TabId } from "@/components/TopNav";
import PoliciesView from "@/components/PoliciesView";
import VendorsView from "@/components/VendorsView";

const TABS = [
  { id: "flagged" as const, label: "Flagged" },
  { id: "approved" as const, label: "Approved" },
  // Rejected closes out the request-decision group; reference-data tabs
  // (Policies / Vendors) live to the right of a vertical separator.
  { id: "rejected" as const, label: "Rejected", dividerAfter: true },
  { id: "policies" as const, label: "Policies" },
  { id: "vendors" as const, label: "Vendors" },
];

type RequestsFilter = "flagged" | "approved" | "rejected";

const REQUEST_TABS: ReadonlySet<TabId> = new Set<TabId>([
  "flagged",
  "approved",
  "rejected",
]);

/** Map a final decision to the matching request tab, if any. */
function tabForDecision(decision: FinalDecision): RequestsFilter | null {
  if (decision === "approve") return "approved";
  if (decision === "reject") return "rejected";
  if (decision === "flag-for-review") return "flagged";
  return null;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("flagged");

  return (
    <div className="flex flex-col h-screen">
      <TopNav tabs={TABS} activeId={activeTab} onSelect={setActiveTab} />
      <main className="flex-1 overflow-hidden">
        {REQUEST_TABS.has(activeTab) && (
          <RequestsView
            filter={activeTab as RequestsFilter}
            onActiveTabChange={setActiveTab}
          />
        )}
        {activeTab === "policies" && (
          <div className="h-full overflow-y-auto custom-scrollbar">
            <PoliciesView />
          </div>
        )}
        {activeTab === "vendors" && (
          <div className="h-full overflow-y-auto custom-scrollbar">
            <VendorsView />
          </div>
        )}
      </main>
    </div>
  );
}

interface RequestsViewProps {
  filter: RequestsFilter;
  onActiveTabChange: (tab: TabId) => void;
}

/** Match a request to a tab by its derived final decision. */
function matchesFilter(decision: FinalDecision, filter: RequestsFilter): boolean {
  switch (filter) {
    case "flagged":
      return decision === "flag-for-review";
    case "approved":
      return decision === "approve";
    case "rejected":
      return decision === "reject";
  }
}

function RequestsView({ filter, onActiveTabChange }: RequestsViewProps) {
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [assessments, setAssessments] = useState<AssessmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);

  useEffect(() => {
    Promise.all([fetchRequests(), fetchAllAssessments()])
      .then(([reqs, asmts]) => {
        setRequests(reqs);
        setAssessments(asmts);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      requests.filter((r) =>
        matchesFilter(decisionForRequest(r.id, assessments), filter),
      ),
    [requests, assessments, filter],
  );

  // Whenever the filter or filtered list changes, ensure the selection is
  // valid. Keep the current selection if it's still in view; otherwise pick
  // the most recent in the new subset, or clear if empty.
  useEffect(() => {
    if (filtered.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => {
      if (current && filtered.some((r) => r.id === current)) return current;
      const latest = filtered.reduce((a, b) =>
        a.updated_at > b.updated_at ? a : b,
      );
      return latest.id;
    });
  }, [filtered]);

  const selected = filtered.find((r) => r.id === selectedId) ?? null;

  /** Refresh both lists. Returns the freshly fetched assessments so callers
   * can derive the new request's tab destination synchronously. */
  async function refreshAll(): Promise<AssessmentRecord[]> {
    const [reqs, asmts] = await Promise.all([
      fetchRequests(),
      fetchAllAssessments(),
    ]);
    setRequests(reqs);
    setAssessments(asmts);
    return asmts;
  }

  /** After a create, switch to whatever tab the agent's decision lands in
   * and pre-select the new request — otherwise the user wouldn't see it. */
  async function handleCreated(req: PurchaseRequest) {
    setShowNewForm(false);
    try {
      const asmts = await refreshAll();
      const decision = decisionForRequest(req.id, asmts);
      const targetTab = tabForDecision(decision);
      if (targetTab) onActiveTabChange(targetTab);
      setSelectedId(req.id);
    } catch {
      // Refresh failed — leave the user where they are; the new request
      // will appear once the next refresh succeeds.
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[var(--muted)] text-sm">Loading requests...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <p className="text-red-600 font-medium">Failed to load requests</p>
          <p className="text-[var(--muted)] text-sm mt-1">{error}</p>
          <p className="text-[var(--muted-light)] text-xs mt-4">
            Make sure the API is running on http://localhost:8000
          </p>
        </div>
      </div>
    );
  }

  const headings: Record<RequestsFilter, { title: string; count: string; empty: string }> = {
    flagged: {
      title: "Flagged for Review",
      count: "flagged",
      empty: "No flagged requests",
    },
    approved: {
      title: "Approved Requests",
      count: "approved",
      empty: "No approved requests yet",
    },
    rejected: {
      title: "Rejected Requests",
      count: "rejected",
      empty: "No rejected requests yet",
    },
  };
  const { title, count, empty } = headings[filter];

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-[420px] min-w-[420px] bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col">
        <div className="px-4 py-4 border-b border-[var(--border)]">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-semibold tracking-tight text-[var(--foreground)]">{title}</h2>
            <button
              onClick={() => setShowNewForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent)] text-white text-xs font-semibold rounded-lg shadow-xs hover:bg-[var(--accent-hover)] hover:shadow-sm transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              New Request
            </button>
          </div>
          <p className="text-xs text-[var(--muted)] font-medium">
            <span className="text-[var(--foreground-soft)] font-semibold">{filtered.length}</span> {count}
          </p>
        </div>

        {filtered.length === 0 ? (
          <div className="flex-1 flex items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
            {empty}
          </div>
        ) : (
          <RequestList
            requests={filtered}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        )}
      </div>

      {/* Detail pane */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {selected ? (
          <RequestDetail request={selected} onRequestUpdated={() => { void refreshAll(); }} />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--muted)] text-sm">
            {filtered.length === 0
              ? empty
              : "Select a request to view details"}
          </div>
        )}
      </div>

      {/* Slide-over for new request */}
      <SlideOver open={showNewForm} onClose={() => setShowNewForm(false)} title="New Purchase Request">
        <NewRequestForm
          onCreated={handleCreated}
          onCancel={() => setShowNewForm(false)}
        />
      </SlideOver>
    </div>
  );
}
