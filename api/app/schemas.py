from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Side = Literal["left", "right"]


class PoseLandmarkResponse(BaseModel):
    name: str
    x: float
    y: float
    z: float
    visibility: float


class PoseFrameResponse(BaseModel):
    time_seconds: float
    landmarks: list[PoseLandmarkResponse]


class PoseTraceResponse(BaseModel):
    schema_version: int = 1
    source: str
    movement_key: str
    side: Side
    width: int
    height: int
    fps: float
    duration_seconds: float
    sampled_frames: int
    frames: list[PoseFrameResponse] = Field(default_factory=list)


class CaptureQualityResponse(BaseModel):
    schema_version: int = 1
    status: Literal["good", "warning", "unavailable"] = "unavailable"
    overlay_available: bool = False
    source: str = "legacy"
    sampled_frames: int = 0
    detection_rate: float = 0.0
    required_landmark_visibility: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=lambda: ["legacy_capture_no_pose_quality"])
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0


class ConsentRequest(BaseModel):
    notice_version: str = Field(min_length=1, max_length=80)
    voluntary_wellness: Literal[True]
    purpose_limited: Literal[True]
    no_employment_decision: Literal[True]
    video_retention_acknowledged: Literal[True]

    @field_validator("notice_version")
    @classmethod
    def normalize_notice_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("notice_version is required")
        return normalized


class AssessmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    consent: ConsentRequest

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name is required")
        return normalized


class CaptureResponse(BaseModel):
    movement_key: str
    side: Side
    score: int
    detected_faults: list[str]
    confidence: float
    metrics: dict[str, float] = Field(default_factory=dict)
    source: str
    pose_trace: PoseTraceResponse | None = None
    quality: CaptureQualityResponse = Field(default_factory=CaptureQualityResponse)


class DraftCaptureResponse(CaptureResponse):
    id: str
    assessment_id: str
    client_capture_id: str
    original_filename: str | None = None
    content_type: str | None = None
    file_size_bytes: int
    created_at: datetime
    expires_at: datetime
    video_url: str | None = None
    video_deleted_at: datetime | None = None


class CaptureFinalizePayload(BaseModel):
    score: int = Field(ge=0, le=3)
    detected_faults: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    pose_trace: PoseTraceResponse | None = None
    quality: CaptureQualityResponse | None = None


class FinalizeMovementRequest(BaseModel):
    right: CaptureFinalizePayload | None = None
    left: CaptureFinalizePayload | None = None


class MovementResultResponse(BaseModel):
    id: str
    assessment_id: str
    movement_key: str
    right_score: int | None
    left_score: int | None
    final_score: int
    detected_faults: dict[str, list[str]]
    app_metrics: dict[str, float] | None = None
    pose_trace: PoseTraceResponse | None = None
    quality: CaptureQualityResponse | None = None
    provider_score: int | None = None
    provider_note: str | None = None
    review_status: str = "unreviewed"


class AssessmentSummaryResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    total_score: int
    score_band: str
    consent_notice_version: str | None = None
    consent_accepted_at: datetime | None = None
    privacy_posture: str = "voluntary_ergonomic_wellness"
    retention_expires_at: datetime | None = None


class AssessmentDetailResponse(AssessmentSummaryResponse):
    movement_results: list[MovementResultResponse]
    consent_scope: dict[str, bool] | None = None


class MovementDefinitionResponse(BaseModel):
    key: str
    label: str
    sides: list[str]
    instructions: str
    capture_tips: list[str]


class ProviderReviewRequest(BaseModel):
    provider_score: int = Field(ge=0, le=3)
    provider_note: str | None = None
