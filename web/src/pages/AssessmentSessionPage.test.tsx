import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { AssessmentSessionPage } from "./AssessmentSessionPage";

const apiMocks = vi.hoisted(() => ({
  uploadCapture: vi.fn(async (_assessmentId, movementKey, side) => ({
    movement_key: movementKey,
    side,
    score: 2,
    detected_faults: side === "right" ? ["shoulder_drift"] : [],
    confidence: 0.41,
    metrics: {},
    source: "fallback"
  })),
  submitManualScore: vi.fn(),
  listDraftCaptures: vi.fn(async () => [] as unknown[]),
  finalizeMovement: vi.fn(async () => ({
    id: "assessment-1",
    name: "Jordan",
    created_at: "2026-04-16T12:00:00Z",
    scoring_mode: "ai_assisted",
    total_score: 2,
    score_band: "High opportunity for improvement",
    consent_notice_version: "hma-privacy-notice-v1",
    consent_accepted_at: "2026-04-16T12:00:00Z",
    privacy_posture: "voluntary_ergonomic_wellness",
    retention_expires_at: "2027-04-16T12:00:00Z",
    movement_results: [
      {
        id: "movement-1",
        assessment_id: "assessment-1",
        movement_key: "cervical_rotation",
        right_score: 2,
        left_score: 2,
        final_score: 2,
        app_score_available: true,
        detected_faults: {
          right: ["shoulder_drift"],
          left: [],
          summary: ["shoulder_drift"]
        },
        app_metrics: null,
        provider_score: null,
        provider_right_score: null,
        provider_left_score: null,
        provider_final_score: null,
        provider_faults: null,
        provider_note: null,
        review_reason: null,
        review_status: "unreviewed",
        reviewed_at: null,
        effective_right_score: 2,
        effective_left_score: 2,
        effective_final_score: 2
      }
    ]
  }))
}));

vi.mock("../lib/api", () => ({
  getAssessment: vi.fn(async () => ({
    id: "assessment-1",
    name: "Jordan",
    created_at: "2026-04-16T12:00:00Z",
    scoring_mode: "ai_assisted",
    total_score: 0,
    score_band: "High opportunity for improvement",
    consent_notice_version: "hma-privacy-notice-v1",
    consent_accepted_at: "2026-04-16T12:00:00Z",
    privacy_posture: "voluntary_ergonomic_wellness",
    retention_expires_at: "2027-04-16T12:00:00Z",
    movement_results: []
  })),
  listMovements: vi.fn(async () => [
    {
      key: "cervical_rotation",
      label: "Cervical Rotation",
      sides: ["right", "left"],
      instructions: "Turn your head.",
      capture_tips: ["Keep shoulders visible."]
    },
    {
      key: "trunk_rotation",
      label: "Trunk Rotation",
      sides: ["right", "left"],
      instructions: "Rotate the trunk.",
      capture_tips: ["Keep the feet quiet."]
    }
  ]),
  uploadCapture: apiMocks.uploadCapture,
  submitManualScore: apiMocks.submitManualScore,
  listDraftCaptures: apiMocks.listDraftCaptures,
  finalizeMovement: apiMocks.finalizeMovement
}));

describe("AssessmentSessionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.listDraftCaptures.mockResolvedValue([]);
    apiMocks.submitManualScore.mockReset();
  });

  it("analyzes both sides and saves the movement result", async () => {
    render(
      <MemoryRouter initialEntries={["/assessments/assessment-1"]}>
        <Routes>
          <Route path="/assessments/:assessmentId" element={<AssessmentSessionPage />} />
          <Route path="/assessments/:assessmentId/results" element={<div>results</div>} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { name: "Cervical Rotation" });

    const testFile = new File(["video"], "capture.webm", { type: "video/webm" });
    const rightSection = screen.getByText("Right-side capture").closest("section");
    const leftSection = screen.getByText("Left-side capture").closest("section");

    expect(rightSection).not.toBeNull();
    expect(leftSection).not.toBeNull();

    fireEvent.change(screen.getByLabelText(/right upload fallback/i), {
      target: { files: [testFile] }
    });
    fireEvent.click(within(rightSection as HTMLElement).getByRole("button", { name: /analyze capture/i }));

    await waitFor(() => {
      expect(apiMocks.uploadCapture).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.uploadCapture).toHaveBeenNthCalledWith(
      1,
      "assessment-1",
      "cervical_rotation",
      "right",
      testFile
    );

    fireEvent.change(screen.getByLabelText(/left upload fallback/i), {
      target: { files: [testFile] }
    });
    fireEvent.click(within(leftSection as HTMLElement).getByRole("button", { name: /analyze capture/i }));

    await waitFor(() => {
      expect(apiMocks.uploadCapture).toHaveBeenCalledTimes(2);
    });
    expect(apiMocks.uploadCapture).toHaveBeenNthCalledWith(
      2,
      "assessment-1",
      "cervical_rotation",
      "left",
      testFile
    );

    fireEvent.click(screen.getByRole("button", { name: /save movement score/i }));

    await waitFor(() => {
      expect(apiMocks.finalizeMovement).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("heading", { name: "Trunk Rotation" })).toBeInTheDocument();
    });
  });

  it("requires both sides before saving a movement result", async () => {
    render(
      <MemoryRouter initialEntries={["/assessments/assessment-1"]}>
        <Routes>
          <Route path="/assessments/:assessmentId" element={<AssessmentSessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { name: "Cervical Rotation" });

    const testFile = new File(["video"], "capture.webm", { type: "video/webm" });
    const rightSection = screen.getByText("Right-side capture").closest("section");

    expect(rightSection).not.toBeNull();

    fireEvent.change(screen.getByLabelText(/right upload fallback/i), {
      target: { files: [testFile] }
    });
    fireEvent.click(within(rightSection as HTMLElement).getByRole("button", { name: /analyze capture/i }));

    await waitFor(() => {
      expect(apiMocks.uploadCapture).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: /save movement score/i }));

    expect(apiMocks.finalizeMovement).not.toHaveBeenCalled();
    expect(screen.getByText("Complete a manual score or analyzed capture for each side before saving this movement.")).toBeInTheDocument();
  });

  it("loads mobile draft captures and finalizes them", async () => {
    apiMocks.listDraftCaptures.mockResolvedValue([
      {
        id: "draft-right",
        assessment_id: "assessment-1",
        movement_key: "cervical_rotation",
        side: "right",
        client_capture_id: "client-right",
        score: 3,
        detected_faults: [],
        confidence: 0.82,
        metrics: {},
        source: "mediapipe",
        original_filename: "right.webm",
        content_type: "video/webm",
        file_size_bytes: 10,
        created_at: "2026-04-16T12:00:00Z",
        expires_at: "2026-04-23T12:00:00Z",
        video_url: "/api/video/right",
        video_deleted_at: null
      },
      {
        id: "draft-left",
        assessment_id: "assessment-1",
        movement_key: "cervical_rotation",
        side: "left",
        client_capture_id: "client-left",
        score: 2,
        detected_faults: ["shoulder_drift"],
        confidence: 0.78,
        metrics: {},
        source: "mediapipe",
        original_filename: "left.webm",
        content_type: "video/webm",
        file_size_bytes: 10,
        created_at: "2026-04-16T12:01:00Z",
        expires_at: "2026-04-23T12:01:00Z",
        video_url: "/api/video/left",
        video_deleted_at: null
      }
    ]);

    render(
      <MemoryRouter initialEntries={["/assessments/assessment-1"]}>
        <Routes>
          <Route path="/assessments/:assessmentId" element={<AssessmentSessionPage />} />
          <Route path="/assessments/:assessmentId/results" element={<div>results</div>} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { name: "Cervical Rotation" });
    expect(await screen.findByText("Score 3/3")).toBeInTheDocument();
    expect(screen.getByText("Score 2/3")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /save movement score/i }));

    await waitFor(() => {
      expect(apiMocks.finalizeMovement).toHaveBeenCalledTimes(1);
    });
  });
});
