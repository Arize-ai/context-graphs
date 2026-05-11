"use client";

/** Read-only grid of policies fetched from `/api/policies`. */

import { useEffect, useState } from "react";
import { fetchPolicies } from "@/lib/api";
import type { Policy } from "@/lib/types";

export default function PoliciesView() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPolicies()
      .then(setPolicies)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <ViewLoading label="Loading policies..." />;
  }

  if (error) {
    return <ViewError message={error} />;
  }

  return (
    <div className="max-w-4xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-[var(--foreground)]">Procurement Policies</h2>
        <p className="text-sm text-[var(--muted)] mt-1">
          Policies in effect.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {policies.map((policy) => (
          <PolicyCard key={policy.name} policy={policy} />
        ))}
      </div>
    </div>
  );
}

function PolicyCard({ policy }: { policy: Policy }) {
  return (
    <article className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 shadow-xs hover:shadow-sm transition-shadow">
      <h3 className="text-sm font-semibold tracking-tight text-[var(--foreground)]">{policy.name}</h3>
      <p className="text-xs text-[var(--muted)] mt-1 leading-relaxed">
        {policy.description}
      </p>
      <ul className="mt-4 space-y-2">
        {policy.rules.map((rule, idx) => (
          <li
            key={idx}
            className="text-sm text-[var(--foreground-soft)] flex items-start gap-2.5 leading-relaxed"
          >
            <span className="text-[var(--accent)] flex-shrink-0 mt-2 w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
            <span>{rule}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function ViewLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-[var(--muted)] text-sm">{label}</p>
      </div>
    </div>
  );
}

function ViewError({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-md">
        <p className="text-red-700 font-semibold text-sm">Failed to load</p>
        <p className="text-[var(--muted)] text-xs mt-1">{message}</p>
      </div>
    </div>
  );
}
