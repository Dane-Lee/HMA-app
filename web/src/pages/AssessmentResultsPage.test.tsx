import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { AssessmentResultsPage } from "./AssessmentResultsPage";

const apiMocks = vi.hoisted(() => ({
  deleteAssessment: vi.fn(),
  getAssessment: vi.fn(),
  getThresholds: vi.fn(),
  listMovements: vi.fn(),
  submitReview: vi.fn()
}));

vi.mock("../lib/api", () => ({
  deleteAssessment: apiMocks.deleteAssessment,
  getAssessment: apiMocks.getAssessment,
  getThresholds: apiMocks.getThresholds,
  listMovements: apiMocks.listMovements,
  submitReview: apiMocks.submitReview
}));

describe("AssessmentResultsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getAssessment.mockResolvedValue({
      id: "assessment-1",
      name: "Jordan",
      created_at: "2026-04-16T12:00:00Z",
      total_score: 0,
      score_band: "High opportunity for improvement",
      consent_notice_version: "hma-privacy-notice-v1",
      consent_accepted_at: "2026-04-16T12:00:00Z",
      privacy_posture: "voluntary_ergonomic_wellness",
      retention_expires_at: "2027-04-16T12:00:00Z",
      movement_results: []
    });
    apiMocks.getThresholds.mockResolvedValue({});
    apiMocks.listMovements.mockResolvedValue([]);
    apiMocks.deleteAssessment.mockResolvedValue(undefined);
  });

  it("shows privacy posture, retention, provider separation, and delete controls", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={["/assessments/assessment-1/results"]}>
        <Routes>
          <Route path="/assessments/:assessmentId/results" element={<AssessmentResultsPage />} />
          <Route path="/history" element={<div>history</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Jordan" })).toBeInTheDocument();
    expect(screen.getByText(/voluntary and for ergonomic\/wellness screening/i)).toBeInTheDocument();
    expect(screen.getByText(/app scores and provider-reviewed scores are stored separately/i)).toBeInTheDocument();
    expect(screen.getByText("hma-privacy-notice-v1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /delete assessment/i }));

    await waitFor(() => {
      expect(apiMocks.deleteAssessment).toHaveBeenCalledWith("assessment-1");
      expect(screen.getByText("history")).toBeInTheDocument();
    });
  });
});
