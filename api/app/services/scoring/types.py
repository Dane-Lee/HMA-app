from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class VideoContext:
    path: Path
    side: str
    movement_key: str
    file_size_bytes: int
    duration_seconds: float
    frame_count: int
    fps: float
    width: int
    height: int


@dataclass(slots=True)
class MovementFeatures:
    chin_midline_clearance_ratio: float = 0.0
    shoulder_drift_ratio: float = 0.0
    forward_head_ratio: float = 0.0
    neck_path_deviation_ratio: float = 0.0
    excessive_effort_ratio: float = 0.0
    trunk_rotation_angle_degrees: float = 0.0
    lower_extremity_movement_ratio: float = 0.0
    spine_pelvis_deviation_ratio: float = 0.0
    cervical_motion_ratio: float = 0.0
    back_knee_depth_ratio: float = 0.0
    upright_posture_ratio: float = 0.0
    knee_tracking_ratio: float = 0.0
    front_foot_flatness_ratio: float = 0.0
    body_control_ratio: float = 0.0
    balance_loss_ratio: float = 0.0
    body_rotation_ratio: float = 0.0
    foot_collapse_ratio: float = 0.0
    knee_collapse_ratio: float = 0.0
    hip_level_ratio: float = 0.0
    hand_distance_ratio: float = 0.0
    bottom_hand_reach_ratio: float = 0.0
    top_hand_midline_ratio: float = 0.0
    lateral_flexion_ratio: float = 0.0
    rounded_shoulder_ratio: float = 0.0
    finger_walk_ratio: float = 0.0
    debug_metrics: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResult:
    context: VideoContext
    features: MovementFeatures
    source: str


@dataclass(slots=True)
class CaptureScore:
    movement_key: str
    side: str
    score: int
    detected_faults: list[str]
    confidence: float
    metrics: dict[str, float]
    source: str

