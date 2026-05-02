import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { MobileCapturePage } from "./MobileCapturePage";

const apiMocks = vi.hoisted(() => ({
  createMobileCaptureAssessment: vi.fn(),
  getAssessment: vi.fn(),
  listDraftCaptures: vi.fn(),
  listMovements: vi.fn(),
  uploadDraftCapture: vi.fn()
}));

vi.mock("../lib/api", () => ({
  createMobileCaptureAssessment: apiMocks.createMobileCaptureAssessment,
  getAssessment: apiMocks.getAssessment,
  listDraftCaptures: apiMocks.listDraftCaptures,
  listMovements: apiMocks.listMovements,
  uploadDraftCapture: apiMocks.uploadDraftCapture
}));

describe("MobileCapturePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    apiMocks.listMovements.mockResolvedValue([
      {
        key: "cervical_rotation",
        label: "Cervical Rotation",
        sides: ["right", "left"],
        instructions: "Turn your head.",
        capture_tips: []
      }
    ]);
    apiMocks.createMobileCaptureAssessment.mockResolvedValue({
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
    apiMocks.listDraftCaptures.mockResolvedValue([]);
    apiMocks.uploadDraftCapture.mockImplementation(async (_assessmentId, movementKey, side, clientCaptureId) => ({
      id: `draft-${side}`,
      assessment_id: "assessment-1",
      movement_key: movementKey,
      side,
      client_capture_id: clientCaptureId,
      score: side === "right" ? 3 : 2,
      detected_faults: [],
      confidence: 0.8,
      metrics: {},
      source: "mediapipe",
      original_filename: `${side}.webm`,
      content_type: "video/webm",
      file_size_bytes: 10,
      created_at: "2026-04-16T12:00:00Z",
      expires_at: "2026-04-23T12:00:00Z",
      video_url: `/api/video/${side}`,
      video_deleted_at: null
    }));
  });

  it("creates a mobile session and uploads a side capture", async () => {
    render(
      <MemoryRouter>
        <MobileCapturePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("button", { name: /create mobile capture session/i })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/enter participant name or id/i), {
      target: { value: "Jordan" }
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /create mobile capture session/i }));

    expect(await screen.findByRole("heading", { name: "Jordan" })).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 2/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cervical Rotation" })).toBeInTheDocument();
    expect(screen.getAllByText("Right side").length).toBeGreaterThan(0);

    const file = new File(["video"], "right.webm", { type: "video/webm" });
    fireEvent.change(screen.getByLabelText(/record clip/i), {
      target: { files: [file] }
    });
    expect(screen.getByText(/ready to upload/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /confirm upload/i }));

    await waitFor(() => {
      expect(apiMocks.uploadDraftCapture).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.uploadDraftCapture).toHaveBeenCalledWith(
      "assessment-1",
      "cervical_rotation",
      "right",
      expect.any(String),
      file
    );
    expect(apiMocks.createMobileCaptureAssessment).toHaveBeenCalledWith(
      "Jordan",
      expect.objectContaining({
        notice_version: "hma-privacy-notice-v1",
        video_retention_acknowledged: true
      })
    );
    expect(await screen.findByText(/step 2 of 2/i)).toBeInTheDocument();
    expect(screen.getAllByText("Left side").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(await screen.findByText(/uploaded: score 3\/3/i)).toBeInTheDocument();
  });

  it("lets the user delete local queued clips after upload failure", async () => {
    apiMocks.uploadDraftCapture.mockRejectedValueOnce(new Error("offline"));

    render(
      <MemoryRouter>
        <MobileCapturePage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/enter participant name or id/i), {
      target: { value: "Jordan" }
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /create mobile capture session/i }));

    expect(await screen.findByRole("heading", { name: "Jordan" })).toBeInTheDocument();

    const file = new File(["video"], "right.webm", { type: "video/webm" });
    fireEvent.change(screen.getByLabelText(/record clip/i), {
      target: { files: [file] }
    });
    fireEvent.click(screen.getByRole("button", { name: /confirm upload/i }));

    expect(await screen.findByText(/1 local queued clip on this device/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /delete local queued clips/i }));

    await waitFor(() => {
      expect(screen.queryByText(/local queued clip/i)).not.toBeInTheDocument();
    });
  });
});
