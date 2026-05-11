/**
 * Tests for `OverrideForm`. The override goes through the agent via
 * `overrideRequest` and now requires both a reviewer name and a
 * reasoning. These tests verify the call shape and form behavior
 * without exercising the real agent.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import OverrideForm from "../OverrideForm";
import * as api from "@/lib/api";
import type { EvaluatorAssessment } from "@/lib/types";

const baseAssessment: EvaluatorAssessment = {
  request_id: "PR-001",
  policy_compliance: "compliant",
  policy_details: "x",
  budget_status: "ok",
  vendor_status: "approved",
  duplicate_check: "",
  history_notes: "",
  recommendation: "approve",
  recommendation_reasoning: "fine",
  confidence: "high",
  risk_factors: [],
};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

function getNameInput(): HTMLInputElement {
  return screen.getByPlaceholderText(/Vera Fye/) as HTMLInputElement;
}

function getReasoningTextarea(): HTMLTextAreaElement {
  return screen.getByPlaceholderText(/Why are you overriding/) as HTMLTextAreaElement;
}

describe("OverrideForm", () => {
  it("disables submit buttons until both name and reasoning are non-empty", () => {
    render(<OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();

    fireEvent.change(getReasoningTextarea(), {
      target: { value: "vendor history fine" },
    });
    // Reasoning alone isn't enough — name is also required.
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();

    fireEvent.change(getNameInput(), { target: { value: "Vera Fye" } });
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("posts override with decision, reasoning, and reviewer_name", async () => {
    const spy = vi.spyOn(api, "overrideRequest").mockResolvedValue({} as never);
    const onSubmitted = vi.fn();

    render(
      <OverrideForm assessment={baseAssessment} onSubmitted={onSubmitted} />,
    );
    fireEvent.change(getNameInput(), { target: { value: "Vera Fye" } });
    fireEvent.change(getReasoningTextarea(), {
      target: { value: "agree with agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(spy).toHaveBeenCalledWith("PR-001", {
      decision: "approve",
      reasoning: "agree with agent",
      reviewer_name: "Vera Fye",
    });
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("trims whitespace from name and reasoning before sending", async () => {
    const spy = vi.spyOn(api, "overrideRequest").mockResolvedValue({} as never);

    render(
      <OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />,
    );
    fireEvent.change(getNameInput(), { target: { value: "  Vera Fye  " } });
    fireEvent.change(getReasoningTextarea(), {
      target: { value: "   vendor SLA concerns   " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(spy.mock.calls[0][1]).toEqual({
      decision: "reject",
      reasoning: "vendor SLA concerns",
      reviewer_name: "Vera Fye",
    });
  });

  it("does not submit when reasoning is whitespace only", () => {
    const spy = vi.spyOn(api, "overrideRequest").mockResolvedValue({} as never);
    render(<OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />);
    fireEvent.change(getNameInput(), { target: { value: "Vera Fye" } });
    fireEvent.change(getReasoningTextarea(), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("does not submit when reviewer name is whitespace only", () => {
    const spy = vi.spyOn(api, "overrideRequest").mockResolvedValue({} as never);
    render(<OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />);
    fireEvent.change(getNameInput(), { target: { value: "   " } });
    fireEvent.change(getReasoningTextarea(), { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("persists the reviewer name to localStorage and reuses it on next mount", async () => {
    vi.spyOn(api, "overrideRequest").mockResolvedValue({} as never);

    const { unmount } = render(
      <OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />,
    );
    fireEvent.change(getNameInput(), { target: { value: "Vera Fye" } });
    fireEvent.change(getReasoningTextarea(), { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(window.localStorage.getItem("procurement-ui:reviewer-name")).toBe(
        "Vera Fye",
      ),
    );

    unmount();
    render(<OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />);
    expect(getNameInput().value).toBe("Vera Fye");
  });

  it("displays an error message when the API call fails", async () => {
    vi.spyOn(api, "overrideRequest").mockRejectedValue(new Error("boom"));
    render(<OverrideForm assessment={baseAssessment} onSubmitted={() => {}} />);
    fireEvent.change(getNameInput(), { target: { value: "Vera Fye" } });
    fireEvent.change(getReasoningTextarea(), { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
