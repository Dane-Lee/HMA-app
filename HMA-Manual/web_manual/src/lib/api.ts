import type {
  ConsentPayload,
  IssuedUploadSession,
  ManualAssessmentDetail,
  ManualAssessmentSummary,
  ManualReviewVideo,
  ManualScorePayload,
  MovementDefinition,
  Provider,
  SelfMe,
  Side
} from "./types";

const API_BASE = import.meta.env.VITE_MANUAL_API_BASE_URL ?? "";

export type AuthStatus = {
  authenticated: boolean;
  provider: Provider | null;
  mfa_required: boolean;
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
    const body = await response.json().catch(async () => ({ detail: await response.text() }));
    throw new Error((body as { detail?: string }).detail || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getAuthStatus() {
  return request<AuthStatus>("/api/auth");
}

export function login(username: string, password: string, mfaCode?: string) {
  return request<{ ok: true; provider: Provider }>("/api/auth", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, mfa_code: mfaCode || undefined })
  });
}

export function logout() {
  return fetch(buildApiUrl("/api/auth"), {
    method: "DELETE",
    credentials: "include"
  });
}

export function listMovements() {
  return request<MovementDefinition[]>("/api/movements");
}

export function createAssessment(participantName: string, consent: ConsentPayload) {
  return request<ManualAssessmentDetail>("/api/assessments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ participant_name: participantName, consent })
  });
}

export function listAssessments() {
  return request<ManualAssessmentSummary[]>("/api/assessments");
}

export function getAssessment(assessmentId: string) {
  return request<ManualAssessmentDetail>(`/api/assessments/${assessmentId}`);
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

export function saveManualScore(assessmentId: string, movementKey: string, payload: ManualScorePayload) {
  return request<ManualAssessmentDetail>(`/api/assessments/${assessmentId}/movements/${movementKey}/manual-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function uploadReviewVideo(
  assessmentId: string,
  movementKey: string,
  side: Side,
  file: File,
  clientVideoId: string
) {
  const body = new FormData();
  body.append("movement_key", movementKey);
  body.append("side", side);
  body.append("client_video_id", clientVideoId);
  body.append("video", file);
  const response = await fetch(buildApiUrl(`/api/assessments/${assessmentId}/review-videos`), {
    method: "POST",
    body,
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return normalizeReviewVideo((await response.json()) as ManualReviewVideo);
}

export function deleteReviewVideo(assessmentId: string, videoId: string) {
  return fetch(buildApiUrl(`/api/assessments/${assessmentId}/review-videos/${videoId}`), {
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

export function deleteAllReviewVideos(assessmentId: string) {
  return request<{ deleted_count: number; assessment: ManualAssessmentDetail }>(`/api/assessments/${assessmentId}/delete-videos`, {
    method: "POST"
  });
}

export function completeAssessment(assessmentId: string, confirmDeleteVideos: boolean) {
  return request<ManualAssessmentDetail>(`/api/assessments/${assessmentId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_delete_videos: confirmDeleteVideos })
  });
}

export function issueUploadSession(
  assessmentId: string,
  employee: { name: string; employer: string; email?: string; notes?: string }
) {
  return request<IssuedUploadSession>(`/api/assessments/${assessmentId}/upload-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee })
  });
}

export function consumeUploadLink(token: string) {
  return request<SelfMe>("/api/self/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token })
  });
}

export function getSelfMe() {
  return request<SelfMe>("/api/self/me").then(normalizeSelfMe);
}

export async function uploadSelfReviewVideo(movementKey: string, side: Side, file: File, clientVideoId: string) {
  const body = new FormData();
  body.append("movement_key", movementKey);
  body.append("side", side);
  body.append("client_video_id", clientVideoId);
  body.append("video", file);
  const response = await fetch(buildApiUrl("/api/self/review-videos"), {
    method: "POST",
    body,
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return normalizeReviewVideo((await response.json()) as ManualReviewVideo);
}

export function submitSelfUploads() {
  return request<{ ok: true }>("/api/self/submit", { method: "POST" });
}

export function endSelfSession() {
  return fetch(buildApiUrl("/api/self/session"), {
    method: "DELETE",
    credentials: "include"
  });
}

export function normalizeAssessment(assessment: ManualAssessmentDetail): ManualAssessmentDetail {
  return {
    ...assessment,
    review_videos: assessment.review_videos.map(normalizeReviewVideo)
  };
}

function normalizeSelfMe(me: SelfMe): SelfMe {
  return {
    ...me,
    assessment: normalizeAssessment(me.assessment),
    review_videos: me.review_videos.map(normalizeReviewVideo)
  };
}

function normalizeReviewVideo(video: ManualReviewVideo): ManualReviewVideo {
  return {
    ...video,
    video_url: video.video_url ? buildApiUrl(video.video_url) : null
  };
}
