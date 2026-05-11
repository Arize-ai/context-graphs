/**
 * Tests for `RequestList`. The interesting behavior is the sort logic —
 * default sort, sort-toggle direction on repeat clicks, urgency / status
 * ranking.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import RequestList from "../RequestList";
import type { PurchaseRequest } from "@/lib/types";

function makeRequest(over: Partial<PurchaseRequest>): PurchaseRequest {
  return {
    id: "PR-001",
    requester: "Test",
    department: "Engineering",
    item: "An item",
    vendor: "TechFlow",
    amount: 1000,
    justification: "j",
    urgency: "routine",
    status: "pending",
    created_at: "2026-04-01T00:00:00",
    updated_at: "2026-04-01T00:00:00",
    ...over,
  };
}

describe("RequestList sorting", () => {
  it("renders all requests", () => {
    const reqs = [
      makeRequest({ id: "PR-001", item: "Alpha" }),
      makeRequest({ id: "PR-002", item: "Bravo" }),
    ];
    render(<RequestList requests={reqs} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Bravo")).toBeInTheDocument();
  });

  it("defaults to updated_at descending — most recent first", () => {
    const reqs = [
      makeRequest({ id: "PR-001", item: "Old", updated_at: "2026-01-01T00:00:00" }),
      makeRequest({ id: "PR-002", item: "New", updated_at: "2026-04-01T00:00:00" }),
    ];
    render(<RequestList requests={reqs} selectedId={null} onSelect={() => {}} />);
    const items = screen.getAllByText(/Old|New/);
    expect(items[0]).toHaveTextContent("New");
    expect(items[1]).toHaveTextContent("Old");
  });

  it("sorts by amount descending when Amount is clicked", () => {
    const reqs = [
      makeRequest({ id: "PR-001", item: "Cheap", amount: 100 }),
      makeRequest({ id: "PR-002", item: "Expensive", amount: 50000 }),
    ];
    render(<RequestList requests={reqs} selectedId={null} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Amount/ }));
    const items = screen.getAllByText(/Cheap|Expensive/);
    expect(items[0]).toHaveTextContent("Expensive");
    expect(items[1]).toHaveTextContent("Cheap");
  });

  it("toggles direction when same field clicked twice", () => {
    const reqs = [
      makeRequest({ id: "PR-001", item: "Cheap", amount: 100 }),
      makeRequest({ id: "PR-002", item: "Expensive", amount: 50000 }),
    ];
    render(<RequestList requests={reqs} selectedId={null} onSelect={() => {}} />);
    const amountBtn = screen.getByRole("button", { name: /Amount/ });
    fireEvent.click(amountBtn); // desc
    fireEvent.click(amountBtn); // asc
    const items = screen.getAllByText(/Cheap|Expensive/);
    expect(items[0]).toHaveTextContent("Cheap");
  });

  it("sorts by urgency placing emergency above urgent above routine", () => {
    const reqs = [
      makeRequest({ id: "PR-001", item: "Routine job", urgency: "routine" }),
      makeRequest({ id: "PR-002", item: "Emergency job", urgency: "emergency" }),
      makeRequest({ id: "PR-003", item: "Urgent job", urgency: "urgent" }),
    ];
    render(<RequestList requests={reqs} selectedId={null} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Urgency/ }));
    const items = screen.getAllByText(/job/);
    expect(items[0]).toHaveTextContent("Emergency");
    expect(items[1]).toHaveTextContent("Urgent");
    expect(items[2]).toHaveTextContent("Routine");
  });

  it("calls onSelect with the clicked request id", () => {
    const reqs = [makeRequest({ id: "PR-007", item: "Click me" })];
    const onSelect = vi.fn();
    render(<RequestList requests={reqs} selectedId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Click me"));
    expect(onSelect).toHaveBeenCalledWith("PR-007");
  });
});
