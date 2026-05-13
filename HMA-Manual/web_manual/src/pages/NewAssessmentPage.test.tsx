import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { NewAssessmentPage } from "./NewAssessmentPage";

const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(async () => ({
    id: "manual-1",
    participant_name: "Jordan",
    status: "draft",
    total_score: 0,
    score_band: "High opportunity for improvement",
    created_at: new Date().toISOString(),
    retention_expires_at: null,
    completed_at: null,
    videos_deleted_at: null,
    remaining_video_count: 0,
    consent_notice_version: "test",
    consent_scope: {},
    employee_id: null,
    movement_results: [],
    review_videos: [],
    upload_sessions: []
  }))
}));

vi.mock("../lib/api", () => ({
  createAssessment: apiMocks.createAssessment
}));

describe("NewAssessmentPage", () => {
  it("creates a manual assessment without scoring-mode choices", async () => {
    render(
      <MemoryRouter initialEntries={["/assessments/new"]}>
        <Routes>
          <Route path="/assessments/new" element={<NewAssessmentPage />} />
          <Route path="/assessments/:assessmentId" element={<p>Manual session</p>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText(/AI assisted/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Analyze capture/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/participant name/i), { target: { value: "Jordan" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /create manual assessment/i }));

    await waitFor(() => {
      expect(apiMocks.createAssessment).toHaveBeenCalled();
    });
    expect(await screen.findByText("Manual session")).toBeInTheDocument();
  });
});
