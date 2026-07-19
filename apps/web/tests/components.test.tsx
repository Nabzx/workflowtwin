import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DraftReview } from "../src/components/DraftReview";
import { EvidenceChart } from "../src/components/EvidenceChart";
import { FictionalNotice } from "../src/components/FictionalNotice";
import { MetricCard } from "../src/components/MetricCard";
import { draft, metrics, recommendation } from "./fixtures";

const mutateAsync = vi.fn();
vi.mock("../src/api/queries", () => ({
  useEditDraft: () => ({ isPending: false, mutateAsync }),
  useApproveDraft: () => ({ isPending: false, mutateAsync }),
  useRejectDraft: () => ({ isPending: false, mutateAsync }),
  useCancelDraft: () => ({ isPending: false, mutateAsync }),
  useReviewRecommendation: () => ({ isPending: false, mutateAsync }),
}));

describe("shared evidence components", () => {
  it("renders metric meaning and supporting note", () => {
    render(<MetricCard label="Detector precision" value="96.6" unit="%" note="Recommendation only" />);
    expect(screen.getByText("Detector precision")).toBeVisible();
    expect(screen.getByText("Recommendation only")).toBeVisible();
  });

  it("always identifies fictional data", () => {
    render(<FictionalNotice />);
    expect(screen.getByText("Fictional demonstration")).toBeVisible();
    expect(screen.getByText(/every record/)).toBeVisible();
  });

  it("provides a textual chart summary", async () => {
    render(<EvidenceChart series={metrics.referral_sources[0]} />);
    await userEvent.click(screen.getByText("Accessible data summary"));
    expect(screen.getByText(/GP practice:/).closest("li")).toHaveTextContent("51.80 %");
  });
});

describe("draft review", () => {
  it("blocks forbidden clinical content before mutation", async () => {
    render(<DraftReview recommendation={recommendation} draft={draft} onAction={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit draft" }));
    const body = screen.getByLabelText("Draft body");
    await userEvent.clear(body);
    await userEvent.type(body, "Add diagnosis. Human review is required.");
    await userEvent.click(screen.getByRole("button", { name: "Save revision" }));
    expect(screen.getByRole("status")).toHaveTextContent("Remove prohibited clinical");
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("shows every supported reviewer command and no send control", () => {
    render(<DraftReview recommendation={recommendation} draft={draft} onAction={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve fictional task" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Request context" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Reject" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
  });
});
