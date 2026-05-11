"use client";

/**
 * Sidebar list of purchase requests with click-to-select and a sort bar.
 *
 * Sort fields: amount, urgency, status, created_at, updated_at. Numeric/date
 * fields default to descending; categorical fields ascending. Repeated
 * clicks on the active field toggle direction.
 */

import { useMemo, useState } from "react";
import type { PurchaseRequest } from "@/lib/types";

interface Props {
  requests: PurchaseRequest[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

type SortField = "id" | "amount" | "department" | "urgency" | "status" | "created_at" | "updated_at";
type SortDir = "asc" | "desc";

const urgencyDot: Record<string, string> = {
  routine: "bg-gray-300",
  urgent: "bg-amber-400",
  emergency: "bg-red-500",
};

const urgencyRank: Record<string, number> = { emergency: 0, urgent: 1, routine: 2 };
const statusRank: Record<string, number> = { pending: 0, processing: 1, completed: 2 };

const sortOptions: { field: SortField; label: string }[] = [
  { field: "amount", label: "Amount" },
  { field: "urgency", label: "Urgency" },
  { field: "status", label: "Status" },
  { field: "created_at", label: "Created" },
  { field: "updated_at", label: "Updated" },
];

function compare(a: PurchaseRequest, b: PurchaseRequest, field: SortField): number {
  switch (field) {
    case "id":
      return a.id.localeCompare(b.id);
    case "amount":
      return a.amount - b.amount;
    case "department":
      return a.department.localeCompare(b.department);
    case "urgency":
      return urgencyRank[a.urgency] - urgencyRank[b.urgency];
    case "status":
      return statusRank[a.status] - statusRank[b.status];
    case "created_at":
      return a.created_at.localeCompare(b.created_at);
    case "updated_at":
      return a.updated_at.localeCompare(b.updated_at);
  }
}

function formatCompact(amount: number): string {
  const abs = Math.abs(amount);
  const formatted =
    abs >= 1000
      ? `$${(abs / 1000).toFixed(abs % 1000 === 0 ? 0 : 1)}k`
      : `$${abs}`;
  return amount < 0 ? `(${formatted})` : formatted;
}

export default function RequestList({ requests, selectedId, onSelect }: Props) {
  const [sortField, setSortField] = useState<SortField>("updated_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const mult = sortDir === "asc" ? 1 : -1;
    return [...requests].sort((a, b) => mult * compare(a, b, sortField));
  }, [requests, sortField, sortDir]);

  function handleSort(field: SortField) {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "amount" || field === "created_at" || field === "updated_at" ? "desc" : "asc");
    }
  }

  return (
    <>
      {/* Sort bar */}
      <div
        role="toolbar"
        aria-label="Sort requests"
        className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border)] bg-[var(--surface-muted)]"
      >
        {sortOptions.map(({ field, label }) => {
          const active = sortField === field;
          return (
            <button
              key={field}
              onClick={() => handleSort(field)}
              className={`flex items-center gap-0.5 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent-active)] shadow-xs"
                  : "text-[var(--muted)] hover:bg-white hover:text-[var(--foreground-soft)]"
              }`}
            >
              {label}
              {active && (
                <svg
                  className={`w-3 h-3 transition-transform ${sortDir === "desc" ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
                </svg>
              )}
            </button>
          );
        })}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {sorted.map((req) => {
          const isSelected = req.id === selectedId;
          return (
            <button
              key={req.id}
              onClick={() => onSelect(req.id)}
              className={`w-full text-left px-4 py-3 border-b border-[var(--border)] transition-colors ${
                isSelected
                  ? "bg-[var(--accent-soft)] border-l-[3px] border-l-[var(--accent)]"
                  : "hover:bg-[var(--surface-muted)] border-l-[3px] border-l-transparent"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-xs font-mono font-semibold ${isSelected ? "text-[var(--accent-active)]" : "text-[var(--muted)]"}`}>
                      {req.id}
                    </span>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${urgencyDot[req.urgency]}`} />
                  </div>
                  <p className="text-sm font-medium truncate leading-snug text-[var(--foreground)]">
                    {req.item}
                  </p>
                  <p className="text-xs text-[var(--muted)] mt-0.5 truncate">
                    {req.requester} &middot; {req.department}
                  </p>
                </div>
                <span className="text-sm font-mono font-semibold tabular-nums flex-shrink-0 mt-0.5 text-[var(--foreground)]">
                  {formatCompact(req.amount)}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </>
  );
}
