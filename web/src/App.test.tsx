import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const apiMocks = vi.hoisted(() => ({
  authenticateWithPin: vi.fn(),
  consumeMagicLink: vi.fn(),
  createAssessment: vi.fn(),
  createEmployee: vi.fn(),
  getAuthStatus: vi.fn(),
  createMobileCaptureAssessment: vi.fn(),
  deleteAssessment: vi.fn(),
  endSelfSession: vi.fn(),
  finalizeMovement: vi.fn(),
  getAssessment: vi.fn(),
  getSelfMe: vi.fn(),
  getThresholds: vi.fn(),
  issueMagicLink: vi.fn(),
  listAssessments: vi.fn(),
  listCalibrationSuggestions: vi.fn(),
  listDraftCaptures: vi.fn(),
  listMovements: vi.fn(),
  approveCalibrationSuggestion: vi.fn(),
  rejectCalibrationSuggestion: vi.fn(),
  submitManualScore: vi.fn(),
  submitReview: vi.fn(),
  uploadCapture: vi.fn(),
  uploadDraftCapture: vi.fn()
}));

vi.mock("./lib/api", () => ({
  authenticateWithPin: apiMocks.authenticateWithPin,
  consumeMagicLink: apiMocks.consumeMagicLink,
  createAssessment: apiMocks.createAssessment,
  createEmployee: apiMocks.createEmployee,
  getAuthStatus: apiMocks.getAuthStatus,
  createMobileCaptureAssessment: apiMocks.createMobileCaptureAssessment,
  deleteAssessment: apiMocks.deleteAssessment,
  endSelfSession: apiMocks.endSelfSession,
  finalizeMovement: apiMocks.finalizeMovement,
  getAssessment: apiMocks.getAssessment,
  getSelfMe: apiMocks.getSelfMe,
  getThresholds: apiMocks.getThresholds,
  issueMagicLink: apiMocks.issueMagicLink,
  listAssessments: apiMocks.listAssessments,
  listCalibrationSuggestions: apiMocks.listCalibrationSuggestions,
  listDraftCaptures: apiMocks.listDraftCaptures,
  listMovements: apiMocks.listMovements,
  approveCalibrationSuggestion: apiMocks.approveCalibrationSuggestion,
  rejectCalibrationSuggestion: apiMocks.rejectCalibrationSuggestion,
  submitManualScore: apiMocks.submitManualScore,
  submitReview: apiMocks.submitReview,
  uploadCapture: apiMocks.uploadCapture,
  uploadDraftCapture: apiMocks.uploadDraftCapture
}));

describe("App", () => {
  beforeEach(() => {
    apiMocks.authenticateWithPin.mockReset();
    apiMocks.consumeMagicLink.mockReset();
    apiMocks.createAssessment.mockReset();
    apiMocks.createEmployee.mockReset();
    apiMocks.getAuthStatus.mockReset();
    apiMocks.createMobileCaptureAssessment.mockReset();
    apiMocks.deleteAssessment.mockReset();
    apiMocks.endSelfSession.mockReset();
    apiMocks.finalizeMovement.mockReset();
    apiMocks.getAssessment.mockReset();
    apiMocks.getSelfMe.mockReset();
    apiMocks.getThresholds.mockReset();
    apiMocks.issueMagicLink.mockReset();
    apiMocks.listAssessments.mockReset();
    apiMocks.listCalibrationSuggestions.mockReset();
    apiMocks.listDraftCaptures.mockReset();
    apiMocks.listMovements.mockReset();
    apiMocks.approveCalibrationSuggestion.mockReset();
    apiMocks.rejectCalibrationSuggestion.mockReset();
    apiMocks.submitManualScore.mockReset();
    apiMocks.submitReview.mockReset();
    apiMocks.uploadCapture.mockReset();
    apiMocks.uploadDraftCapture.mockReset();
    apiMocks.authenticateWithPin.mockResolvedValue(undefined);
    apiMocks.getThresholds.mockResolvedValue({});
    apiMocks.listAssessments.mockResolvedValue([]);
    apiMocks.listCalibrationSuggestions.mockResolvedValue([]);
    apiMocks.listDraftCaptures.mockResolvedValue([]);
    apiMocks.listMovements.mockResolvedValue([]);
    localStorage.clear();
  });

  it("renders the PIN gate when auth is required", async () => {
    apiMocks.getAuthStatus.mockResolvedValue({
      auth_required: true,
      authenticated: false
    });

    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /enter access pin/i })).toBeInTheDocument();
  });

  it("shows a backend unavailable state and retries auth bootstrap", async () => {
    apiMocks.getAuthStatus
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        auth_required: true,
        authenticated: false
      });

    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /start the local api server/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry connection/i }));

    await waitFor(() => {
      expect(apiMocks.getAuthStatus).toHaveBeenCalledTimes(2);
      expect(screen.getByRole("heading", { name: /enter access pin/i })).toBeInTheDocument();
    });
  });

  it("shows mode selection after successful PIN unlock and opens the main program", async () => {
    apiMocks.getAuthStatus.mockResolvedValue({
      auth_required: true,
      authenticated: false
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    fireEvent.change(await screen.findByLabelText(/access pin/i), {
      target: { value: "5380" }
    });
    fireEvent.click(screen.getByRole("button", { name: /unlock/i }));

    expect(await screen.findByRole("heading", { name: /choose workflow/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /main program/i }));

    expect(await screen.findByRole("heading", { name: /begin on-site hma/i })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(within(nav).getByRole("link", { name: /mobile capture/i })).toBeInTheDocument();
  });

  it("routes from mode selection to mobile capture", async () => {
    apiMocks.getAuthStatus.mockResolvedValue({
      auth_required: false,
      authenticated: true
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /choose workflow/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /mobile capture/i }));

    expect(await screen.findByRole("heading", { name: /capture videos on this device/i })).toBeInTheDocument();
  });

  it("allows direct mobile capture entry after auth without showing mode selection", async () => {
    apiMocks.getAuthStatus.mockResolvedValue({
      auth_required: false,
      authenticated: true
    });

    render(
      <MemoryRouter initialEntries={["/mobile-capture"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /capture videos on this device/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /choose workflow/i })).not.toBeInTheDocument();
  });
});
