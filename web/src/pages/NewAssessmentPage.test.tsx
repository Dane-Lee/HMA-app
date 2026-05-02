import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { NewAssessmentPage } from "./NewAssessmentPage";

const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(async () => ({
    id: "assessment-1",
    name: "Taylor",
    created_at: "2026-04-16T12:00:00Z",
    total_score: 0,
    score_band: "High opportunity for improvement",
    consent_notice_version: "hma-privacy-notice-v1",
    consent_accepted_at: "2026-04-16T12:00:00Z",
    privacy_posture: "voluntary_ergonomic_wellness",
    retention_expires_at: "2027-04-16T12:00:00Z",
    movement_results: []
  }))
}));

vi.mock("../lib/api", () => ({
  createAssessment: apiMocks.createAssessment
}));

describe("NewAssessmentPage", () => {
  it("creates an assessment and navigates to the session flow", async () => {
    render(
      <MemoryRouter initialEntries={["/assessments/new"]}>
        <Routes>
          <Route path="/assessments/new" element={<NewAssessmentPage />} />
          <Route path="/assessments/:assessmentId" element={<div>session</div>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/enter participant name or id/i), {
      target: { value: "Taylor" }
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /create assessment/i }));

    await waitFor(() => {
      expect(apiMocks.createAssessment).toHaveBeenCalledWith(
        "Taylor",
        expect.objectContaining({
          notice_version: "hma-privacy-notice-v1",
          voluntary_wellness: true,
          purpose_limited: true,
          no_employment_decision: true,
          video_retention_acknowledged: true
        })
      );
      expect(screen.getByText("session")).toBeInTheDocument();
    });
  });

  it("requires the privacy acknowledgement before creation", () => {
    render(
      <MemoryRouter initialEntries={["/assessments/new"]}>
        <Routes>
          <Route path="/assessments/new" element={<NewAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/enter participant name or id/i), {
      target: { value: "Taylor" }
    });

    expect(screen.getByRole("button", { name: /create assessment/i })).toBeDisabled();
  });
});
