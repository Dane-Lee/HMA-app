from __future__ import annotations

from .base import MovementScorer
from ..types import CaptureScore, ExtractionResult


class ShoulderReachBehindBackScorer(MovementScorer):
    key = "shoulder_reach_behind_back"

    def score(self, extraction: ExtractionResult, thresholds: dict[str, float]) -> CaptureScore:
        features = extraction.features
        faults: list[str] = []
        if features.hand_distance_ratio > thresholds["hand_distance_ratio_max"]:
            faults.append("hands_too_far_apart")
        if features.bottom_hand_reach_ratio < thresholds["bottom_hand_reach_ratio_min"]:
            faults.append("bottom_hand_reach_limited")
        if features.top_hand_midline_ratio < thresholds["top_hand_midline_ratio_min"]:
            faults.append("top_hand_not_reaching_midline")
        if features.lateral_flexion_ratio > thresholds["lateral_flexion_ratio_max"]:
            faults.append("lateral_flexion_or_asymmetry")
        if features.rounded_shoulder_ratio > thresholds["rounded_shoulder_ratio_max"]:
            faults.append("rounded_shoulders")
        if features.finger_walk_ratio > thresholds["finger_walk_ratio_max"]:
            faults.append("finger_walking_placeholder")
        return self.build_score(extraction, faults, placeholder_faults=["finger_walking_placeholder"])

