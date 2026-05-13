import type {
  AssessmentDetail,
  AssessmentSummary,
  CalibrationDecisionPayload,
  CalibrationSuggestion,
  ConsentPayload,
  CaptureResult,
  DraftCapture,
  Employee,
  FinalizePayload,
  ManualScorePayload,
  MovementDefinition,
  ProviderReviewPayload,
  ScoringMode,
  SelfMe,
  Side,
  ThresholdsMap
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type AuthStatus = {
  auth_required: boolean;
  authenticated: boolean;
};

function buildApiUrl(path: string) {
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getAuthStatus() {
  return request<AuthStatus>("/api/auth");
}

export type ConsumeMagicLinkResult = {
  ok: true;
  employee: SelfMe["employee"];
};

export async function consumeMagicLink(token: string): Promise<ConsumeMagicLinkResult> {
  let response: Response;
  try {
    response = await fetch(buildApiUrl("/api/self/session"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ token })
    });
  } catch {
    throw new Error("Unable to reach the server. Make sure the app is running.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Link is invalid or expired.");
  }
  return (await response.json()) as ConsumeMagicLinkResult;
}

export function getSelfMe() {
  return request<SelfMe>("/api/self/me");
}

export type IssuedMagicLink = {
  url: string;
  expires_at: string;
};

export function createEmployee(payload: {
  name: string;
  employer: string;
  email?: string;
  notes?: string;
}) {
  return request<Employee>("/api/provider/employees", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function issueMagicLink(employeeId: string) {
  return request<IssuedMagicLink>(
    `/api/provider/employees/${employeeId}/magic-link`,
    { method: "POST" }
  );
}

export function endSelfSession() {
  return fetch(buildApiUrl("/api/self/session"), {
    method: "DELETE",
    credentials: "include"
  }).then((response) => {
    if (!response.ok) {
      return response.text().then((body) => {
        throw new Error(body || `Request failed with status ${response.status}`);
      });
    }
  });
}

export async function authenticateWithPin(pin: string) {
  let response: Response;
  try {
    response = await fetch(buildApiUrl("/api/auth"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ pin })
    });
  } catch {
    throw new Error("Unable to reach the server. Make sure the app is running.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Incorrect PIN.");
  }
}

export function listMovements() {
  return request<MovementDefinition[]>("/api/movements");
}

export function createAssessment(
  name: string,
  consent: ConsentPayload,
  scoringMode: ScoringMode = "ai_assisted"
) {
  return request<AssessmentDetail>("/api/assessments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ name, consent, scoring_mode: scoringMode })
  });
}

export function createMobileCaptureAssessment(name: string, consent: ConsentPayload) {
  return request<AssessmentDetail>("/api/mobile-capture/assessments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ name, consent })
  });
}

export function getAssessment(assessmentId: string) {
  return request<AssessmentDetail>(`/api/assessments/${assessmentId}`);
}

export function listAssessments() {
  return request<AssessmentSummary[]>("/api/assessments");
}

export function deleteAssessment(assessmentId: string) {
  return fetch(buildApiUrl(`/api/assessments/${assessmentId}`), {
    method: "DELETE",
    credentials: "include"
  }).then((response) => {
    if (!response.ok) {
      return response.text().then((body) => {
        throw new Error(body || `Request failed with status ${response.status}`);
      });
    }
  });
}

const UPLOAD_TIMEOUT_MS = 90_000;

export async function uploadCapture(
  assessmentId: string,
  movementKey: string,
  side: Side,
  file: File
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
  const body = new FormData();
  body.append("side", side);
  body.append("video", file);
  try {
    const response = await fetch(
      buildApiUrl(`/api/assessments/${assessmentId}/movements/${movementKey}/captures`),
      { method: "POST", body, signal: controller.signal, credentials: "include" }
    );
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return (await response.json()) as CaptureResult;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Upload timed out after 90 seconds. Check your connection and try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function uploadDraftCapture(
  assessmentId: string,
  movementKey: string,
  side: Side,
  clientCaptureId: string,
  file: File
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
  const body = new FormData();
  body.append("movement_key", movementKey);
  body.append("side", side);
  body.append("client_capture_id", clientCaptureId);
  body.append("video", file);
  try {
    const response = await fetch(buildApiUrl(`/api/assessments/${assessmentId}/draft-captures`), {
      method: "POST",
      body,
      signal: controller.signal,
      credentials: "include"
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return normalizeDraftCapture(await response.json());
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Upload timed out after 90 seconds. Check your connection and try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function listDraftCaptures(assessmentId: string) {
  const captures = await request<DraftCapture[]>(`/api/assessments/${assessmentId}/draft-captures`);
  return captures.map(normalizeDraftCapture);
}

export function deleteDraftCapture(assessmentId: string, captureId: string) {
  return fetch(buildApiUrl(`/api/assessments/${assessmentId}/draft-captures/${captureId}`), {
    method: "DELETE",
    credentials: "include"
  }).then((response) => {
    if (!response.ok) {
      return response.text().then((body) => {
        throw new Error(body || `Request failed with status ${response.status}`);
      });
    }
  });
}

function normalizeDraftCapture(capture: DraftCapture): DraftCapture {
  return {
    ...capture,
    video_url: capture.video_url ? buildApiUrl(capture.video_url) : null
  };
}

export function finalizeMovement(
  assessmentId: string,
  movementKey: string,
  payload: FinalizePayload
) {
  return request<AssessmentDetail>(
    `/api/assessments/${assessmentId}/movements/${movementKey}/finalize`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    }
  );
}

export function getThresholds() {
  return request<ThresholdsMap>("/api/thresholds");
}

export function submitReview(
  assessmentId: string,
  movementKey: string,
  payload: ProviderReviewPayload
) {
  return request<AssessmentDetail>(
    `/api/assessments/${assessmentId}/movements/${movementKey}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export function submitManualScore(
  assessmentId: string,
  movementKey: string,
  payload: ManualScorePayload
) {
  return request<AssessmentDetail>(
    `/api/assessments/${assessmentId}/movements/${movementKey}/manual-score`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export function listCalibrationSuggestions() {
  return request<CalibrationSuggestion[]>("/api/calibration/suggestions");
}

export function approveCalibrationSuggestion(payload: CalibrationDecisionPayload) {
  return request<{ ok: true; thresholds: ThresholdsMap }>("/api/calibration/suggestions/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function rejectCalibrationSuggestion(payload: CalibrationDecisionPayload) {
  return request<{ ok: true }>("/api/calibration/suggestions/reject", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
