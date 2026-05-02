from __future__ import annotations

from .base import MovementScorer
from ..types import CaptureScore, ExtractionResult


class ForwardLungeScorer(MovementScorer):
    key = "forward_lunge"

    def score(self, extraction: ExtractionResult, thresholds: dict[str, float]) -> CaptureScore:
        features = extraction.features
        faults: list[str] = []
        if features.back_knee_depth_ratio < thresholds["back_knee_depth_ratio_min"]:
            faults.append("back_knee_depth_insufficient")
        if features.upright_posture_ratio < thresholds["upright_posture_ratio_min"]:
            faults.append("loss_of_upright_posture")
        if features.knee_tracking_ratio < thresholds["knee_tracking_ratio_min"]:
            faults.append("front_knee_tracking_fault")
        if features.front_foot_flatness_ratio < thresholds["front_foot_flatness_ratio_min"]:
            faults.append("front_foot_not_flat")
        if features.body_control_ratio < thresholds["body_control_ratio_min"]:
            faults.append("loss_of_body_control")
        if features.excessive_effort_ratio > thresholds["excessive_effort_ratio_max"]:
            faults.append("excessive_effort_placeholder")
        return self.build_score(extraction, faults, placeholder_faults=["excessive_effort_placeholder"])

