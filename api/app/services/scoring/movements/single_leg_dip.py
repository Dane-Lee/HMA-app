from __future__ import annotations

from .base import MovementScorer
from ..types import CaptureScore, ExtractionResult


class SingleLegDipScorer(MovementScorer):
    key = "single_leg_dip"

    def score(self, extraction: ExtractionResult, thresholds: dict[str, float]) -> CaptureScore:
        features = extraction.features
        faults: list[str] = []
        if features.balance_loss_ratio > thresholds["balance_loss_ratio_max"]:
            faults.append("balance_loss")
        if features.body_rotation_ratio > thresholds["body_rotation_ratio_max"]:
            faults.append("body_rotation")
        if features.foot_collapse_ratio > thresholds["foot_collapse_ratio_max"]:
            faults.append("stance_foot_collapse")
        if features.knee_collapse_ratio > thresholds["knee_collapse_ratio_max"]:
            faults.append("stance_knee_collapse")
        if features.hip_level_ratio < thresholds["hip_level_ratio_min"]:
            faults.append("hips_not_level")
        if features.excessive_effort_ratio > thresholds["excessive_effort_ratio_max"]:
            faults.append("excessive_effort_placeholder")
        return self.build_score(extraction, faults, placeholder_faults=["excessive_effort_placeholder"])

