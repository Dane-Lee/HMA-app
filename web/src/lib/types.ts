export type Side = "left" | "right";

export type ConsentPayload = {
  notice_version: string;
  voluntary_wellness: true;
  purpose_limited: true;
  no_employment_decision: true;
  video_retention_acknowledged: true;
};

export type MovementDefinition = {
  key: string;
  label: string;
  sides: Side[];
  instructions: string;
  capture_tips: string[];
};

export type CaptureResult = {
  movement_key: string;
  side: Side;
  score: number;
  detected_faults: string[];
  confidence: number;
  metrics: Record<string, number>;
  source: string;
};

export type DraftCapture = CaptureResult & {
  id: string;
  assessment_id: string;
  client_capture_id: string;
  original_filename: string | null;
  content_type: string | null;
  file_size_bytes: number;
  created_at: string;
  expires_at: string;
  video_url: string | null;
  video_deleted_at: string | null;
};

export type FinalizePayload = {
  left?: {
    score: number;
    detected_faults: string[];
    metrics?: Record<string, number>;
  };
  right?: {
    score: number;
    detected_faults: string[];
    metrics?: Record<string, number>;
  };
};

export type MovementResult = {
  id: string;
  assessment_id: string;
  movement_key: string;
  right_score: number | null;
  left_score: number | null;
  final_score: number;
  detected_faults: Record<string, string[]>;
  app_metrics: Record<string, number> | null;
  provider_score: number | null;
  provider_note: string | null;
  review_status: "unreviewed" | "reviewed";
};

export type AssessmentSummary = {
  id: string;
  name: string;
  created_at: string;
  total_score: number;
  score_band: string;
  consent_notice_version: string | null;
  consent_accepted_at: string | null;
  privacy_posture: string;
  retention_expires_at: string | null;
};

export type AssessmentDetail = AssessmentSummary & {
  movement_results: MovementResult[];
  consent_scope?: Record<string, boolean> | null;
};

export type ProviderReviewPayload = {
  provider_score: number;
  provider_note?: string;
};

export type MovementThresholds = Record<string, number>;
export type ThresholdsMap = Record<string, MovementThresholds>;

export type Employee = {
  id: string;
  name: string;
  email: string | null;
  employer: string;
  created_at: string;
  notes: string | null;
};

export type SelfMe = {
  employee: Employee;
  assessment_id: string | null;
};
