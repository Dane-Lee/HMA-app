export type Side = "left" | "right";

export type ConsentPayload = {
  notice_version: string;
  voluntary_wellness: true;
  purpose_limited: true;
  no_employment_decision: true;
  video_retention_acknowledged: true;
};

export type Provider = {
  id: string;
  username: string;
  display_name: string;
  role: string;
  mfa_enabled: boolean;
};

export type MovementDefinition = {
  key: string;
  label: string;
  sides: Side[];
  instructions: string;
  capture_tips: string[];
};

export type ManualMovementResult = {
  id: string;
  assessment_id: string;
  movement_key: string;
  right_score: number | null;
  left_score: number | null;
  final_score: number;
  faults: Record<string, string[]>;
  provider_note: string | null;
  reviewed_at: string;
};

export type ManualReviewVideo = {
  id: string;
  assessment_id: string;
  movement_key: string;
  side: Side;
  original_filename: string | null;
  content_type: string | null;
  file_size_bytes: number;
  upload_source: "provider" | "employee";
  created_at: string;
  expires_at: string;
  deleted_at: string | null;
  deletion_reason: string | null;
  video_url: string | null;
};

export type UploadSessionSummary = {
  id: string;
  employee_id: string;
  assessment_id: string;
  status: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  submitted_at: string | null;
};

export type ManualAssessmentSummary = {
  id: string;
  participant_name: string;
  employee_id: string | null;
  employee_name?: string | null;
  employee_employer?: string | null;
  status: "draft" | "completed" | string;
  total_score: number;
  score_band: string;
  consent_notice_version: string | null;
  consent_scope: Record<string, boolean> | null;
  created_at: string;
  retention_expires_at: string | null;
  completed_at: string | null;
  videos_deleted_at: string | null;
  remaining_video_count: number;
};

export type ManualAssessmentDetail = ManualAssessmentSummary & {
  movement_results: ManualMovementResult[];
  review_videos: ManualReviewVideo[];
  upload_sessions: UploadSessionSummary[];
};

export type ManualSideScorePayload = {
  score: number;
  faults: string[];
};

export type ManualScorePayload = {
  right?: ManualSideScorePayload;
  left?: ManualSideScorePayload;
  provider_note?: string;
};

export type Employee = {
  id: string;
  name: string;
  employer: string;
  email: string | null;
  notes: string | null;
  created_at: string;
};

export type IssuedUploadSession = {
  id: string;
  url: string;
  expires_at: string;
  employee: Employee;
};

export type SelfUploadSession = {
  id: string;
  status: string;
  expires_at: string;
  allowed_slots: Array<{ movement_key: string; side: Side }>;
};

export type SelfMe = {
  employee: Employee;
  assessment: ManualAssessmentDetail;
  upload_session: SelfUploadSession;
  movements: MovementDefinition[];
  review_videos: ManualReviewVideo[];
};
