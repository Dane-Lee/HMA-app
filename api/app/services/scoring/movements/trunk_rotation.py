from __future__ import annotations

from .base import MovementScorer
from ..types import CaptureScore, ExtractionResult


class TrunkRotationScorer(MovementScorer):
    key = "trunk_rotation"

    def score(self, extraction: ExtractionResult, thresholds: dict[str, float]) -> CaptureScore:
        features = extraction.features
        faults: list[str] = []
        if features.trunk_rotation_angle_degrees < thresholds["rotation_angle_min_degrees"]:
            faults.append("rotation_below_45_degrees")
        if features.lower_extremity_movement_ratio > thresholds["lower_extremity_movement_ratio_max"]:
            faults.append("excessive_lower_extremity_movement")
        if features.spine_pelvis_deviation_ratio > thresholds["spine_pelvis_deviation_ratio_max"]:
            faults.append("spine_or_pelvis_deviation")
        if features.cervical_motion_ratio > thresholds["cervical_motion_ratio_max"]:
            faults.append("excessive_cervical_motion")
        if features.excessive_effort_ratio > thresholds["excessive_effort_ratio_max"]:
            faults.append("excessive_effort_placeholder")
        return self.build_score(extraction, faults, placeholder_faults=["excessive_effort_placeholder"])

