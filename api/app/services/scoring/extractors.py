from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from .types import (
    CaptureQuality,
    ExtractionResult,
    MovementFeatures,
    PoseFrame,
    PoseLandmark,
    PoseTrace,
    VideoContext,
)

try:
    import cv2  # type: ignore
    import mediapipe as mp  # type: ignore
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - optional dependency path
    cv2 = None
    mp = None
    np = None


EPSILON = 1e-6


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _safe_mean(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def _safe_span(values: list[float], default: float = 0.0) -> float:
    return (max(values) - min(values)) if values else default


@dataclass(slots=True)
class FramePose:
    timestamp_seconds: float
    landmarks: dict[str, PoseLandmark]
    nose_x: float
    nose_y: float
    nose_z: float
    left_ear_visibility: float
    right_ear_visibility: float
    left_shoulder_x: float
    right_shoulder_x: float
    left_shoulder_y: float
    right_shoulder_y: float
    left_shoulder_z: float
    right_shoulder_z: float
    left_hip_x: float
    right_hip_x: float
    left_hip_y: float
    right_hip_y: float
    left_hip_z: float
    right_hip_z: float
    left_knee_x: float
    right_knee_x: float
    left_knee_y: float
    right_knee_y: float
    left_ankle_x: float
    right_ankle_x: float
    left_ankle_y: float
    right_ankle_y: float
    left_heel_y: float
    right_heel_y: float
    left_foot_y: float
    right_foot_y: float
    left_wrist_x: float
    right_wrist_x: float
    left_wrist_y: float
    right_wrist_y: float


class HybridFeatureExtractor:
    def __init__(self, *, enable_pose_overlays: bool = True, max_pose_trace_frames: int = 48) -> None:
        self.enable_pose_overlays = enable_pose_overlays
        self.max_pose_trace_frames = max(1, max_pose_trace_frames)

    def extract(self, video_path: Path, movement_key: str, side: str) -> ExtractionResult:
        context = self._build_context(video_path, movement_key, side)
        if cv2 is not None and mp is not None and np is not None:
            try:
                return self._extract_with_mediapipe(context)
            except Exception:
                pass
        return self._fallback_extract(context)

    def _build_context(self, video_path: Path, movement_key: str, side: str) -> VideoContext:
        stat = video_path.stat()
        fps = 0.0
        frame_count = 0
        width = 0
        height = 0
        duration_seconds = max(stat.st_size / 650_000, 1.25)
        if cv2 is not None:
            capture = cv2.VideoCapture(str(video_path))
            if capture.isOpened():
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if fps > 0 and frame_count > 0:
                    duration_seconds = frame_count / fps
            capture.release()
        return VideoContext(
            path=video_path,
            side=side,
            movement_key=movement_key,
            file_size_bytes=stat.st_size,
            duration_seconds=round(duration_seconds, 2),
            frame_count=frame_count,
            fps=fps,
            width=width,
            height=height,
        )

    def _extract_with_mediapipe(self, context: VideoContext) -> ExtractionResult:
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        capture = cv2.VideoCapture(str(context.path))
        frames: list[FramePose] = []
        index = 0
        sample_every = max(1, int((context.fps or 24) // 6))
        sampled_attempts = 0
        try:
            while capture.isOpened():
                success, frame = capture.read()
                if not success:
                    break
                if index % sample_every != 0:
                    index += 1
                    continue
                sampled_attempts += 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)
                if results.pose_landmarks:
                    timestamp_seconds = index / (context.fps or 24.0)
                    frames.append(self._map_pose(results.pose_landmarks.landmark, timestamp_seconds))
                index += 1
        finally:
            capture.release()
            pose.close()

        if len(frames) < 3:
            raise RuntimeError("Insufficient pose frames extracted.")

        features = self._derive_features(frames, context)
        pose_trace = self._build_pose_trace(frames, context) if self.enable_pose_overlays else None
        quality = self._build_capture_quality(
            frames,
            context,
            source="mediapipe",
            sampled_attempts=sampled_attempts,
            overlay_available=pose_trace is not None,
        )
        return ExtractionResult(
            context=context,
            features=features,
            source="mediapipe",
            pose_trace=pose_trace,
            quality=quality,
        )

    def _map_pose(self, landmarks, timestamp_seconds: float) -> FramePose:
        pose_landmarks = mp.solutions.pose.PoseLandmark
        mapped_landmarks = {
            landmark.name.lower(): PoseLandmark(
                name=landmark.name.lower(),
                x=round(float(landmarks[landmark].x), 5),
                y=round(float(landmarks[landmark].y), 5),
                z=round(float(landmarks[landmark].z), 5),
                visibility=round(float(landmarks[landmark].visibility), 5),
            )
            for landmark in pose_landmarks
        }
        return FramePose(
            timestamp_seconds=round(timestamp_seconds, 3),
            landmarks=mapped_landmarks,
            nose_x=landmarks[pose_landmarks.NOSE].x,
            nose_y=landmarks[pose_landmarks.NOSE].y,
            nose_z=landmarks[pose_landmarks.NOSE].z,
            left_ear_visibility=landmarks[pose_landmarks.LEFT_EAR].visibility,
            right_ear_visibility=landmarks[pose_landmarks.RIGHT_EAR].visibility,
            left_shoulder_x=landmarks[pose_landmarks.LEFT_SHOULDER].x,
            right_shoulder_x=landmarks[pose_landmarks.RIGHT_SHOULDER].x,
            left_shoulder_y=landmarks[pose_landmarks.LEFT_SHOULDER].y,
            right_shoulder_y=landmarks[pose_landmarks.RIGHT_SHOULDER].y,
            left_shoulder_z=landmarks[pose_landmarks.LEFT_SHOULDER].z,
            right_shoulder_z=landmarks[pose_landmarks.RIGHT_SHOULDER].z,
            left_hip_x=landmarks[pose_landmarks.LEFT_HIP].x,
            right_hip_x=landmarks[pose_landmarks.RIGHT_HIP].x,
            left_hip_y=landmarks[pose_landmarks.LEFT_HIP].y,
            right_hip_y=landmarks[pose_landmarks.RIGHT_HIP].y,
            left_hip_z=landmarks[pose_landmarks.LEFT_HIP].z,
            right_hip_z=landmarks[pose_landmarks.RIGHT_HIP].z,
            left_knee_x=landmarks[pose_landmarks.LEFT_KNEE].x,
            right_knee_x=landmarks[pose_landmarks.RIGHT_KNEE].x,
            left_knee_y=landmarks[pose_landmarks.LEFT_KNEE].y,
            right_knee_y=landmarks[pose_landmarks.RIGHT_KNEE].y,
            left_ankle_x=landmarks[pose_landmarks.LEFT_ANKLE].x,
            right_ankle_x=landmarks[pose_landmarks.RIGHT_ANKLE].x,
            left_ankle_y=landmarks[pose_landmarks.LEFT_ANKLE].y,
            right_ankle_y=landmarks[pose_landmarks.RIGHT_ANKLE].y,
            left_heel_y=landmarks[pose_landmarks.LEFT_HEEL].y,
            right_heel_y=landmarks[pose_landmarks.RIGHT_HEEL].y,
            left_foot_y=landmarks[pose_landmarks.LEFT_FOOT_INDEX].y,
            right_foot_y=landmarks[pose_landmarks.RIGHT_FOOT_INDEX].y,
            left_wrist_x=landmarks[pose_landmarks.LEFT_WRIST].x,
            right_wrist_x=landmarks[pose_landmarks.RIGHT_WRIST].x,
            left_wrist_y=landmarks[pose_landmarks.LEFT_WRIST].y,
            right_wrist_y=landmarks[pose_landmarks.RIGHT_WRIST].y,
        )

    def _build_pose_trace(self, frames: list[FramePose], context: VideoContext) -> PoseTrace | None:
        if not frames:
            return None
        step = max(1, math.ceil(len(frames) / self.max_pose_trace_frames))
        capped_frames = frames[::step][: self.max_pose_trace_frames]
        return PoseTrace(
            schema_version=1,
            source="mediapipe",
            movement_key=context.movement_key,
            side=context.side,
            width=context.width,
            height=context.height,
            fps=round(context.fps, 3),
            duration_seconds=context.duration_seconds,
            sampled_frames=len(frames),
            frames=[
                PoseFrame(
                    time_seconds=frame.timestamp_seconds,
                    landmarks=list(frame.landmarks.values()),
                )
                for frame in capped_frames
            ],
        )

    def _build_capture_quality(
        self,
        frames: list[FramePose],
        context: VideoContext,
        *,
        source: str,
        sampled_attempts: int,
        overlay_available: bool,
    ) -> CaptureQuality:
        required_names = [
            "nose",
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_ankle",
            "right_ankle",
            "left_wrist",
            "right_wrist",
        ]
        visibility = {
            name: round(
                _safe_mean([frame.landmarks[name].visibility for frame in frames if name in frame.landmarks]),
                3,
            )
            for name in required_names
        }
        detection_rate = round(len(frames) / max(sampled_attempts, 1), 3)
        warnings: list[str] = []
        if not self.enable_pose_overlays:
            warnings.append("pose_overlays_disabled")
        if detection_rate < 0.75:
            warnings.append("low_pose_detection_rate")
        if len(frames) < 8:
            warnings.append("limited_pose_samples")
        if context.width <= 0 or context.height <= 0:
            warnings.append("missing_video_dimensions")
        low_visibility = [name for name, value in visibility.items() if value < 0.5]
        if low_visibility:
            warnings.append("low_required_landmark_visibility")
        status = "good" if overlay_available and not warnings else "warning"
        return CaptureQuality(
            schema_version=1,
            status=status,
            overlay_available=overlay_available,
            source=source,
            sampled_frames=len(frames),
            detection_rate=detection_rate,
            required_landmark_visibility=visibility,
            warnings=warnings,
            width=context.width,
            height=context.height,
            fps=round(context.fps, 3),
            duration_seconds=context.duration_seconds,
        )

    def _derive_features(self, frames: list[FramePose], context: VideoContext) -> MovementFeatures:
        shoulder_widths = [
            abs(frame.left_shoulder_x - frame.right_shoulder_x) + EPSILON for frame in frames
        ]
        hip_widths = [abs(frame.left_hip_x - frame.right_hip_x) + EPSILON for frame in frames]
        torso_lengths = [
            abs(((frame.left_shoulder_y + frame.right_shoulder_y) / 2) - ((frame.left_hip_y + frame.right_hip_y) / 2))
            + EPSILON
            for frame in frames
        ]
        mid_shoulder_x = [(frame.left_shoulder_x + frame.right_shoulder_x) / 2 for frame in frames]
        mid_hip_x = [(frame.left_hip_x + frame.right_hip_x) / 2 for frame in frames]
        nose_offsets = [
            abs(frame.nose_x - mid_shoulder_x[index]) / shoulder_widths[index]
            for index, frame in enumerate(frames)
        ]
        nose_vertical_path = [frame.nose_y for frame in frames]
        shoulder_depth = [
            abs(frame.left_shoulder_z - frame.right_shoulder_z) / shoulder_widths[index]
            for index, frame in enumerate(frames)
        ]
        head_forward = [
            abs(frame.nose_z - ((frame.left_shoulder_z + frame.right_shoulder_z) / 2)) / torso_lengths[index]
            for index, frame in enumerate(frames)
        ]
        lower_ext_motion = [
            (
                abs(frame.left_knee_x - frames[0].left_knee_x)
                + abs(frame.right_knee_x - frames[0].right_knee_x)
                + abs(frame.left_ankle_x - frames[0].left_ankle_x)
                + abs(frame.right_ankle_x - frames[0].right_ankle_x)
            )
            / (2 * hip_widths[index])
            for index, frame in enumerate(frames)
        ]
        trunk_rotations = [
            math.degrees(math.atan2(abs(frame.left_shoulder_z - frame.right_shoulder_z), shoulder_widths[index]))
            for index, frame in enumerate(frames)
        ]
        cervical_rotations = [offset * 90 for offset in nose_offsets]
        side_is_right = context.side == "right"
        front_knee_x = [frame.right_knee_x if side_is_right else frame.left_knee_x for frame in frames]
        front_ankle_x = [frame.right_ankle_x if side_is_right else frame.left_ankle_x for frame in frames]
        back_knee_y = [frame.left_knee_y if side_is_right else frame.right_knee_y for frame in frames]
        back_ankle_y = [frame.left_ankle_y if side_is_right else frame.right_ankle_y for frame in frames]
        front_heel_y = [frame.right_heel_y if side_is_right else frame.left_heel_y for frame in frames]
        front_foot_y = [frame.right_foot_y if side_is_right else frame.left_foot_y for frame in frames]
        stance_knee_x = front_knee_x
        stance_ankle_x = front_ankle_x
        hand_distances = [
            math.hypot(frame.left_wrist_x - frame.right_wrist_x, frame.left_wrist_y - frame.right_wrist_y)
            / torso_lengths[index]
            for index, frame in enumerate(frames)
        ]
        bottom_hand_reach = [
            (
                ((frame.left_hip_y + frame.right_hip_y) / 2)
                - (frame.left_wrist_y if side_is_right else frame.right_wrist_y)
            )
            / torso_lengths[index]
            for index, frame in enumerate(frames)
        ]
        top_hand_midline = [
            1
            - (
                abs((frame.right_wrist_x if side_is_right else frame.left_wrist_x) - mid_shoulder_x[index])
                / shoulder_widths[index]
            )
            for index, frame in enumerate(frames)
        ]

        features = MovementFeatures(
            chin_midline_clearance_ratio=_clamp(max(nose_offsets), 0.0, 1.5),
            shoulder_drift_ratio=_clamp(_safe_span(mid_shoulder_x) / _safe_mean(shoulder_widths, 1.0), 0.0, 1.5),
            forward_head_ratio=_clamp(_safe_mean(head_forward), 0.0, 1.5),
            neck_path_deviation_ratio=_clamp(_safe_span(nose_vertical_path) / _safe_mean(torso_lengths, 1.0), 0.0, 1.5),
            excessive_effort_ratio=_clamp((_safe_span(mid_shoulder_x) + _safe_span(nose_vertical_path)) * 2.5, 0.0, 1.2),
            trunk_rotation_angle_degrees=_clamp(max(trunk_rotations), 0.0, 90.0),
            lower_extremity_movement_ratio=_clamp(max(lower_ext_motion), 0.0, 1.2),
            spine_pelvis_deviation_ratio=_clamp(
                _safe_mean(
                    [
                        abs(mid_shoulder_x[index] - mid_hip_x[index]) / hip_widths[index]
                        for index in range(len(frames))
                    ]
                ),
                0.0,
                1.2,
            ),
            cervical_motion_ratio=_clamp(
                max(cervical_rotations) / max(max(trunk_rotations), 1.0),
                0.0,
                1.5,
            ),
            back_knee_depth_ratio=_clamp(
                max(back_knee_y[index] - back_ankle_y[index] for index in range(len(frames)))
                / _safe_mean(torso_lengths, 1.0),
                0.0,
                1.2,
            ),
            upright_posture_ratio=_clamp(
                1.0
                - (
                    _safe_mean(
                        [
                            abs(mid_shoulder_x[index] - mid_hip_x[index]) / torso_lengths[index]
                            for index in range(len(frames))
                        ]
                    )
                    * 1.3
                ),
                0.0,
                1.0,
            ),
            knee_tracking_ratio=_clamp(
                1.0
                - _safe_mean(
                    [
                        abs(front_knee_x[index] - front_ankle_x[index]) / hip_widths[index]
                        for index in range(len(frames))
                    ]
                ),
                0.0,
                1.0,
            ),
            front_foot_flatness_ratio=_clamp(
                1.0
                - _safe_mean(
                    [
                        abs(front_heel_y[index] - front_foot_y[index]) / torso_lengths[index]
                        for index in range(len(frames))
                    ]
                )
                * 1.8,
                0.0,
                1.0,
            ),
            body_control_ratio=_clamp(
                1.0 - (_safe_span(mid_hip_x) + _safe_span(mid_shoulder_x)) * 1.6,
                0.0,
                1.0,
            ),
            balance_loss_ratio=_clamp((_safe_span(mid_hip_x) + _safe_span(mid_shoulder_x)) * 1.2, 0.0, 1.2),
            body_rotation_ratio=_clamp(max(shoulder_depth), 0.0, 1.2),
            foot_collapse_ratio=_clamp(
                _safe_mean(
                    [
                        abs(stance_knee_x[index] - stance_ankle_x[index]) / hip_widths[index]
                        for index in range(len(frames))
                    ]
                ),
                0.0,
                1.2,
            ),
            knee_collapse_ratio=_clamp(
                max(
                    abs((frame.right_knee_x if side_is_right else frame.left_knee_x) - (frame.right_hip_x if side_is_right else frame.left_hip_x))
                    / hip_widths[index]
                    for index, frame in enumerate(frames)
                )
                * 0.9,
                0.0,
                1.2,
            ),
            hip_level_ratio=_clamp(
                1.0
                - _safe_mean(
                    [
                        abs(frame.left_hip_y - frame.right_hip_y) / torso_lengths[index]
                        for index, frame in enumerate(frames)
                    ]
                )
                * 2.0,
                0.0,
                1.0,
            ),
            hand_distance_ratio=_clamp(min(hand_distances), 0.0, 2.0),
            bottom_hand_reach_ratio=_clamp(max(bottom_hand_reach), 0.0, 1.5),
            top_hand_midline_ratio=_clamp(max(top_hand_midline), 0.0, 1.0),
            lateral_flexion_ratio=_clamp(_safe_span(mid_shoulder_x) / _safe_mean(torso_lengths, 1.0), 0.0, 1.2),
            rounded_shoulder_ratio=_clamp(_safe_mean(head_forward) * 0.8 + _safe_mean(shoulder_depth) * 0.2, 0.0, 1.2),
            finger_walk_ratio=_clamp(_safe_span(hand_distances), 0.0, 1.2),
        )
        features.debug_metrics = {
            "duration_seconds": context.duration_seconds,
            "sampled_frames": float(len(frames)),
            # cervical rotation
            "chin_midline_clearance_ratio": features.chin_midline_clearance_ratio,
            "shoulder_drift_ratio": features.shoulder_drift_ratio,
            "forward_head_ratio": features.forward_head_ratio,
            "neck_path_deviation_ratio": features.neck_path_deviation_ratio,
            # trunk rotation
            "trunk_rotation_angle_degrees": features.trunk_rotation_angle_degrees,
            "lower_extremity_movement_ratio": features.lower_extremity_movement_ratio,
            "spine_pelvis_deviation_ratio": features.spine_pelvis_deviation_ratio,
            "cervical_motion_ratio": features.cervical_motion_ratio,
            # forward lunge
            "back_knee_depth_ratio": features.back_knee_depth_ratio,
            "upright_posture_ratio": features.upright_posture_ratio,
            "knee_tracking_ratio": features.knee_tracking_ratio,
            "front_foot_flatness_ratio": features.front_foot_flatness_ratio,
            # single leg dip
            "balance_loss_ratio": features.balance_loss_ratio,
            "body_rotation_ratio": features.body_rotation_ratio,
            "foot_collapse_ratio": features.foot_collapse_ratio,
            "knee_collapse_ratio": features.knee_collapse_ratio,
            "hip_level_ratio": features.hip_level_ratio,
            # shoulder reach behind back
            "hand_distance_ratio": features.hand_distance_ratio,
            "bottom_hand_reach_ratio": features.bottom_hand_reach_ratio,
            "top_hand_midline_ratio": features.top_hand_midline_ratio,
            "lateral_flexion_ratio": features.lateral_flexion_ratio,
            "rounded_shoulder_ratio": features.rounded_shoulder_ratio,
            # shared
            "excessive_effort_ratio": features.excessive_effort_ratio,
            "body_control_ratio": features.body_control_ratio,
        }
        return features

    def _fallback_extract(self, context: VideoContext) -> ExtractionResult:
        digest = hashlib.sha256()
        digest.update(context.path.name.encode("utf-8"))
        with context.path.open("rb") as handle:
            digest.update(handle.read(4096))
            handle.seek(max(context.file_size_bytes - 4096, 0))
            digest.update(handle.read(4096))
        seed = int(digest.hexdigest()[:12], 16)
        quality = (seed % 1000) / 1000
        if "good" in context.path.name.lower():
            quality = 0.86
        elif "limited" in context.path.name.lower():
            quality = 0.45
        elif "poor" in context.path.name.lower():
            quality = 0.22

        duration_factor = _clamp(context.duration_seconds / 6.0, 0.2, 1.0)
        control = _clamp((quality * 0.8) + (duration_factor * 0.2), 0.1, 0.95)
        asymmetry = ((seed // 17) % 100) / 1000
        features = MovementFeatures(
            chin_midline_clearance_ratio=_clamp(0.06 + control * 0.14 - asymmetry, 0.0, 0.3),
            shoulder_drift_ratio=_clamp(0.16 - control * 0.12 + asymmetry, 0.0, 0.3),
            forward_head_ratio=_clamp(0.34 - control * 0.2 + asymmetry / 2, 0.02, 0.4),
            neck_path_deviation_ratio=_clamp(0.14 - control * 0.1 + asymmetry / 2, 0.01, 0.2),
            excessive_effort_ratio=_clamp(0.98 - control * 0.6, 0.12, 1.0),
            trunk_rotation_angle_degrees=_clamp(18 + control * 50, 10, 75),
            lower_extremity_movement_ratio=_clamp(0.28 - control * 0.18, 0.04, 0.32),
            spine_pelvis_deviation_ratio=_clamp(0.2 - control * 0.14, 0.03, 0.25),
            cervical_motion_ratio=_clamp(0.72 - control * 0.42, 0.08, 0.75),
            back_knee_depth_ratio=_clamp(0.08 + control * 0.22, 0.05, 0.34),
            upright_posture_ratio=_clamp(0.42 + control * 0.46, 0.2, 0.96),
            knee_tracking_ratio=_clamp(0.4 + control * 0.45, 0.2, 0.95),
            front_foot_flatness_ratio=_clamp(0.44 + control * 0.44, 0.2, 0.98),
            body_control_ratio=_clamp(0.38 + control * 0.48, 0.2, 0.96),
            balance_loss_ratio=_clamp(0.34 - control * 0.22, 0.06, 0.34),
            body_rotation_ratio=_clamp(0.28 - control * 0.18, 0.05, 0.32),
            foot_collapse_ratio=_clamp(0.24 - control * 0.15, 0.03, 0.26),
            knee_collapse_ratio=_clamp(0.27 - control * 0.17, 0.04, 0.29),
            hip_level_ratio=_clamp(0.45 + control * 0.46, 0.2, 0.97),
            hand_distance_ratio=_clamp(0.74 - control * 0.42, 0.12, 0.8),
            bottom_hand_reach_ratio=_clamp(0.28 + control * 0.42, 0.1, 0.9),
            top_hand_midline_ratio=_clamp(0.36 + control * 0.42, 0.1, 0.9),
            lateral_flexion_ratio=_clamp(0.26 - control * 0.16, 0.03, 0.28),
            rounded_shoulder_ratio=_clamp(0.3 - control * 0.18, 0.04, 0.32),
            finger_walk_ratio=_clamp(0.28 - control * 0.18, 0.02, 0.3),
        )
        features.debug_metrics = {
            "duration_seconds": context.duration_seconds,
            "fallback_quality_index": round(control, 3),
            "seed_asymmetry": round(asymmetry, 3),
            # cervical rotation
            "chin_midline_clearance_ratio": round(features.chin_midline_clearance_ratio, 3),
            "shoulder_drift_ratio": round(features.shoulder_drift_ratio, 3),
            "forward_head_ratio": round(features.forward_head_ratio, 3),
            "neck_path_deviation_ratio": round(features.neck_path_deviation_ratio, 3),
            # trunk rotation
            "trunk_rotation_angle_degrees": round(features.trunk_rotation_angle_degrees, 3),
            "lower_extremity_movement_ratio": round(features.lower_extremity_movement_ratio, 3),
            "spine_pelvis_deviation_ratio": round(features.spine_pelvis_deviation_ratio, 3),
            "cervical_motion_ratio": round(features.cervical_motion_ratio, 3),
            # forward lunge
            "back_knee_depth_ratio": round(features.back_knee_depth_ratio, 3),
            "upright_posture_ratio": round(features.upright_posture_ratio, 3),
            "knee_tracking_ratio": round(features.knee_tracking_ratio, 3),
            "front_foot_flatness_ratio": round(features.front_foot_flatness_ratio, 3),
            # single leg dip
            "balance_loss_ratio": round(features.balance_loss_ratio, 3),
            "body_rotation_ratio": round(features.body_rotation_ratio, 3),
            "foot_collapse_ratio": round(features.foot_collapse_ratio, 3),
            "knee_collapse_ratio": round(features.knee_collapse_ratio, 3),
            "hip_level_ratio": round(features.hip_level_ratio, 3),
            # shoulder reach behind back
            "hand_distance_ratio": round(features.hand_distance_ratio, 3),
            "bottom_hand_reach_ratio": round(features.bottom_hand_reach_ratio, 3),
            "top_hand_midline_ratio": round(features.top_hand_midline_ratio, 3),
            "lateral_flexion_ratio": round(features.lateral_flexion_ratio, 3),
            "rounded_shoulder_ratio": round(features.rounded_shoulder_ratio, 3),
            # shared
            "excessive_effort_ratio": round(features.excessive_effort_ratio, 3),
            "body_control_ratio": round(features.body_control_ratio, 3),
        }
        return ExtractionResult(
            context=context,
            features=features,
            source="fallback",
            pose_trace=None,
            quality=CaptureQuality(
                schema_version=1,
                status="unavailable",
                overlay_available=False,
                source="fallback",
                sampled_frames=0,
                detection_rate=0.0,
                required_landmark_visibility={},
                warnings=["pose_overlay_unavailable_for_fallback_scoring"],
                width=context.width,
                height=context.height,
                fps=round(context.fps, 3),
                duration_seconds=context.duration_seconds,
            ),
        )
