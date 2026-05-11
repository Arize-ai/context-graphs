"use client";

/**
 * Form for creating a new purchase request. Loads department + vendor
 * options on mount, validates required fields via HTML form constraints,
 * and POSTs to `/api/requests` on submit. Rendered inside a `SlideOver`
 * panel.
 */

import { useState, useEffect, type FormEvent } from "react";
import { createRequest, fetchDepartments, fetchVendors } from "@/lib/api";
import type {
  Department,
  PurchaseRequest,
  PurchaseRequestCreate,
  Urgency,
  Vendor,
} from "@/lib/types";

interface Props {
  onCreated: (req: PurchaseRequest) => void;
  onCancel: () => void;
}

const emptyForm: PurchaseRequestCreate = {
  requester: "",
  department: "",
  item: "",
  vendor: "",
  amount: 0,
  justification: "",
  urgency: "routine",
};

export default function NewRequestForm({ onCreated, onCancel }: Props) {
  const [form, setForm] = useState<PurchaseRequestCreate>(emptyForm);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDepartments().then(setDepartments).catch(() => {});
    fetchVendors().then(setVendors).catch(() => {});
  }, []);

  function update(field: keyof PurchaseRequestCreate, value: string | number) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createRequest(form);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  const labelClass = "block text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-1.5";
  const inputClass =
    "w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-light)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-ring)]";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div>
        <label className={labelClass}>Requester</label>
        <input
          className={inputClass}
          placeholder="Full name"
          required
          value={form.requester}
          onChange={(e) => update("requester", e.target.value)}
        />
      </div>

      <div>
        <label className={labelClass}>Department</label>
        <select
          className={inputClass}
          required
          value={form.department}
          onChange={(e) => update("department", e.target.value)}
        >
          <option value="">Select department</option>
          {departments.map((d) => (
            <option key={d.name} value={d.name}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass}>Item / Service</label>
        <input
          className={inputClass}
          placeholder="What are you purchasing?"
          required
          value={form.item}
          onChange={(e) => update("item", e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Vendor</label>
          <select
            className={inputClass}
            required
            value={form.vendor}
            onChange={(e) => update("vendor", e.target.value)}
          >
            <option value="">Select vendor</option>
            {vendors.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass}>Amount ($)</label>
          <input
            className={inputClass}
            type="number"
            step="0.01"
            placeholder="0.00"
            required
            value={form.amount || ""}
            onChange={(e) => update("amount", parseFloat(e.target.value) || 0)}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>Urgency</label>
        <div className="flex gap-2">
          {(["routine", "urgent", "emergency"] as Urgency[]).map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => update("urgency", level)}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg border transition-all capitalize ${
                form.urgency === level
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-active)] shadow-xs"
                  : "border-[var(--border)] text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground-soft)]"
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className={labelClass}>Business Justification</label>
        <textarea
          className={inputClass}
          rows={4}
          placeholder="Why is this purchase needed?"
          required
          value={form.justification}
          onChange={(e) => update("justification", e.target.value)}
        />
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2">
          <p className="text-red-800 text-xs font-medium">{error}</p>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex-1 py-2.5 bg-[var(--accent)] text-white text-sm font-semibold rounded-lg shadow-xs hover:bg-[var(--accent-hover)] hover:shadow-sm disabled:opacity-50 disabled:shadow-none transition-all"
        >
          {submitting ? "Submitting..." : "Submit Request"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2.5 border border-[var(--border)] bg-[var(--surface)] text-sm font-semibold rounded-lg text-[var(--foreground-soft)] hover:bg-[var(--surface-muted)] transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
