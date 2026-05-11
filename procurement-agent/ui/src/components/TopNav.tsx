"use client";

/**
 * Top tab strip. Five tabs (Flagged / Approved / Rejected / Policies /
 * Vendors) with an active underline. The parent owns the active state and
 * decides how to filter the request list per tab. There is no "Pending"
 * tab — every created request is auto-processed by the agent, so a
 * request always lands in one of the three decision tabs immediately.
 */

export type TabId =
  | "flagged"
  | "approved"
  | "rejected"
  | "policies"
  | "vendors";

interface Tab {
  id: TabId;
  label: string;
  /** Render a vertical separator immediately after this tab. Used to
   *  group the request-decision tabs apart from the reference-data
   *  tabs (Policies / Vendors). */
  dividerAfter?: boolean;
}

interface Props {
  tabs: Tab[];
  activeId: TabId;
  onSelect: (id: TabId) => void;
}

export default function TopNav({ tabs, activeId, onSelect }: Props) {
  return (
    <header className="flex items-center gap-6 px-6 h-14 border-b border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-sm flex-shrink-0 shadow-xs">
      <div className="flex items-center gap-2">
        <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
        <h1 className="text-sm font-semibold tracking-tight text-[var(--foreground)]">
          Procurement
        </h1>
      </div>
      <nav className="flex items-center gap-0.5 h-full">
        {tabs.map((tab) => {
          const active = tab.id === activeId;
          return (
            <div key={tab.id} className="flex items-center h-full">
              <button
                onClick={() => onSelect(tab.id)}
                className={`relative h-full px-3.5 text-[13px] font-semibold transition-colors ${
                  active
                    ? "text-[var(--accent-active)]"
                    : "text-[var(--muted)] hover:text-[var(--foreground)]"
                }`}
              >
                {tab.label}
                {active && (
                  <span className="absolute bottom-0 left-2 right-2 h-[2.5px] bg-[var(--accent)] rounded-t" />
                )}
              </button>
              {tab.dividerAfter && (
                <span
                  aria-hidden="true"
                  className="mx-2 w-px h-5 bg-[var(--border-strong)]"
                />
              )}
            </div>
          );
        })}
      </nav>
    </header>
  );
}
