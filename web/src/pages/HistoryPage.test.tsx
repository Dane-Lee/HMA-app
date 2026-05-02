import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { HistoryPage } from "./HistoryPage";

const apiMocks = vi.hoisted(() => ({
  deleteAssessment: vi.fn(),
  listAssessments: vi.fn()
}));

vi.mock("../lib/api", () => ({
  deleteAssessment: apiMocks.deleteAssessment,
  listAssessments: apiMocks.listAssessments
}));

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.listAssessments.mockResolvedValue([
      {
        id: "assessment-1",
        name: "Jordan",
        created_at: "2026-04-16T12:00:00Z",
        total_score: 3,
        score_band: "High opportunity for improvement",
        consent_notice_version: "hma-privacy-notice-v1",
        consent_accepted_at: "2026-04-16T12:00:00Z",
        privacy_posture: "voluntary_ergonomic_wellness",
        retention_expires_at: "2027-04-16T12:00:00Z"
      }
    ]);
    apiMocks.deleteAssessment.mockResolvedValue(undefined);
  });

  it("shows retention information and removes an assessment through delete control", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Jordan" })).toBeInTheDocument();
    expect(screen.getByText(/voluntary and for ergonomic\/wellness screening/i)).toBeInTheDocument();
    expect(screen.getByText(/retain until/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /delete assessment/i }));

    await waitFor(() => {
      expect(apiMocks.deleteAssessment).toHaveBeenCalledWith("assessment-1");
      expect(screen.queryByRole("heading", { name: "Jordan" })).not.toBeInTheDocument();
    });
  });
});
