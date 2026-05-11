"use client";

/**
 * Vendors view. Groups vendors by status (preferred / approved / suspended /
 * not_listed) and renders each group as a list of cards with the vendor's
 * categories and notes.
 */

import { useEffect, useMemo, useState } from "react";
import { fetchVendors } from "@/lib/api";
import type { Vendor, VendorStatus } from "@/lib/types";

const STATUS_ORDER: VendorStatus[] = ["preferred", "approved", "suspended", "not_listed"];

const statusConfig: Record<VendorStatus, { label: string; bg: string; text: string; border: string; description: string }> = {
  preferred: {
    label: "Preferred",
    bg: "bg-emerald-100",
    text: "text-emerald-800",
    border: "border-emerald-200",
    description: "Go-to vendor for this category under the consolidation directive.",
  },
  approved: {
    label: "Approved",
    bg: "bg-sky-100",
    text: "text-sky-800",
    border: "border-sky-200",
    description: "Passes the vendor check.",
  },
  suspended: {
    label: "Suspended",
    bg: "bg-red-100",
    text: "text-red-800",
    border: "border-red-200",
    description: "Reject any request involving these vendors.",
  },
  not_listed: {
    label: "Not Listed",
    bg: "bg-amber-100",
    text: "text-amber-800",
    border: "border-amber-200",
    description: "Not on the approved list — flagged as non-compliant.",
  },
};

export default function VendorsView() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVendors()
      .then(setVendors)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<VendorStatus, Vendor[]>();
    for (const status of STATUS_ORDER) map.set(status, []);
    for (const vendor of vendors) {
      const list = map.get(vendor.status);
      if (list) list.push(vendor);
    }
    return map;
  }, [vendors]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[var(--muted)] text-sm">Loading vendors...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <p className="text-red-700 font-semibold text-sm">Failed to load</p>
          <p className="text-[var(--muted)] text-xs mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-[var(--foreground)]">Vendors</h2>
        <p className="text-sm text-[var(--muted)] mt-1">
          Known vendors.
        </p>
      </div>

      <div className="space-y-8">
        {STATUS_ORDER.map((status) => {
          const items = grouped.get(status) ?? [];
          if (items.length === 0) return null;
          const cfg = statusConfig[status];
          return (
            <section key={status}>
              <div className="flex items-baseline gap-3 mb-3">
                <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
                  {cfg.label}
                </span>
                <span className="text-xs text-[var(--muted)]">{cfg.description}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {items.map((vendor) => (
                  <VendorCard key={vendor.name} vendor={vendor} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function VendorCard({ vendor }: { vendor: Vendor }) {
  return (
    <article className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-xs hover:shadow-sm transition-shadow">
      <h3 className="text-sm font-semibold tracking-tight text-[var(--foreground)]">{vendor.name}</h3>
      <p className="text-xs text-[var(--muted)] mt-1 font-medium">
        {vendor.categories.join(" · ")}
      </p>
      {vendor.notes && (
        <p className="text-xs text-[var(--muted)] italic mt-2 leading-relaxed">
          {vendor.notes}
        </p>
      )}
    </article>
  );
}
