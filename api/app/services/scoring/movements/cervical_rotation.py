from __future__ import annotations

from .base import MovementScorer
from ..types import CaptureScore, ExtractionResult


class CervicalRotationScorer(MovementScorer):
    key = "cervical_rotation"

    def score(self, extraction: ExtractionResult, thresholds: dict[str, float]) -> CaptureScore:
        features = extraction.features
        faults: list[str] = []
        if features.chin_midline_clearance_ratio < thresholds["chin_midline_clearance_ratio_min"]:
            faults.append("chin_does_not_clear_clavicle_midline")
        if features.shoulder_drift_ratio > thresholds["shoulder_drift_ratio_max"]:
            faults.append("shoulder_drift")
        if features.forward_head_ratio > thresholds["forward_head_ratio_max"]:
            faults.append("forward_head_or_rounded_shoulder_setup")
        if features.neck_path_deviation_ratio > thresholds["neck_path_deviation_ratio_max"]:
            faults.append("neck_deviation_from_midline")
        if features.excessive_effort_ratio > thresholds["excessive_effort_ratio_max"]:
            faults.append("excessive_effort_placeholder")
        return self.build_score(extraction, faults, placeholder_faults=["excessive_effort_placeholder"])

