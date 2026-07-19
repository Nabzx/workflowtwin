import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { EvidencePage } from "../src/pages/EvidencePage";
import { PilotPage } from "../src/pages/PilotPage";
import { SimulationPage } from "../src/pages/SimulationPage";
import { WorkflowPage } from "../src/pages/WorkflowPage";
import { draft, metrics, pilotSummary, recommendation, simulation, workflow } from "./fixtures";

vi.mock("../src/api/queries", () => ({
  useWorkflow: () => ({ isPending: false, error: null, data: workflow, refetch: vi.fn() }),
  useMetrics: () => ({ isPending: false, error: null, data: metrics, refetch: vi.fn() }),
  useSimulation: () => ({ isPending: false, error: null, data: simulation, refetch: vi.fn() }),
  usePilotSummary: () => ({ isPending: false, error: null, data: pilotSummary, refetch: vi.fn() }),
  useRecommendations: () => ({ isPending: false, error: null, data: [recommendation], refetch: vi.fn() }),
  useDrafts: () => ({ isPending: false, error: null, data: [draft], refetch: vi.fn() }),
  useEditDraft: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useApproveDraft: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useRejectDraft: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useCancelDraft: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useReviewRecommendation: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

describe("evidence views", () => {
  it("switches process display modes and exposes variants", async () => {
    render(<WorkflowPage />);
    await userEvent.click(screen.getByRole("button", { name: "Frequency" }));
    expect(screen.getByLabelText(/frequency mode/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Inspect path" }));
    expect(screen.getByLabelText("Selected variant activity sequence")).toBeVisible();
  });

  it("switches evidence cohort views", async () => {
    render(<EvidencePage />);
    await userEvent.click(screen.getByRole("button", { name: "Service line" }));
    expect(screen.getByText("Operational evidence")).toBeVisible();
    expect(screen.getAllByText("First-pass completeness").length).toBeGreaterThan(0);
  });

  it("keeps the adverse simulation inspectable", async () => {
    render(<SimulationPage />);
    await userEvent.click(screen.getByRole("button", { name: /adverse/i }));
    expect(screen.getByText("adverse scenario")).toBeVisible();
    expect(screen.getAllByText("Do not act").length).toBeGreaterThan(0);
  });

  it("shows recommendation safety evidence without a send action", async () => {
    render(<MemoryRouter><PilotPage /></MemoryRouter>);
    expect(await screen.findByText("Completeness review required")).toBeVisible();
    expect(screen.getByText("No future leakage")).toBeVisible();
    expect(screen.queryByRole("button", { name: /^send/i })).not.toBeInTheDocument();
  });
});

