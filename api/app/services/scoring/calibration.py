from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Literal


Direction = Literal["min", "max"]


@dataclass(frozen=True, slots=True)
class CalibrationCheck:
    movement_key: str
    threshold_key: str
    metric_key: str
    direction: Direction
    fault_key: str


CALIBRATION_CHECKS: list[CalibrationCheck] = [
    CalibrationCheck("cervical_rotation", "chin_midline_clearance_ratio_min", "chin_midline_clearance_ratio", "min", "chin_does_not_clear_clavicle_midline"),
    CalibrationCheck("cervical_rotation", "shoulder_drift_ratio_max", "shoulder_drift_ratio", "max", "shoulder_drift"),
    CalibrationCheck("cervical_rotation", "forward_head_ratio_max", "forward_head_ratio", "max", "forward_head_or_rounded_shoulder_setup"),
    CalibrationCheck("cervical_rotation", "neck_path_deviation_ratio_max", "neck_path_deviation_ratio", "max", "neck_deviation_from_midline"),
    CalibrationCheck("trunk_rotation", "rotation_angle_min_degrees", "trunk_rotation_angle_degrees", "min", "rotation_below_45_degrees"),
    CalibrationCheck("trunk_rotation", "lower_extremity_movement_ratio_max", "lower_extremity_movement_ratio", "max", "excessive_lower_extremity_movement"),
    CalibrationCheck("trunk_rotation", "spine_pelvis_deviation_ratio_max", "spine_pelvis_deviation_ratio", "max", "spine_or_pelvis_deviation"),
    CalibrationCheck("trunk_rotation", "cervical_motion_ratio_max", "cervical_motion_ratio", "max", "excessive_cervical_motion"),
    CalibrationCheck("forward_lunge", "back_knee_depth_ratio_min", "back_knee_depth_ratio", "min", "back_knee_depth_insufficient"),
    CalibrationCheck("forward_lunge", "upright_posture_ratio_min", "upright_posture_ratio", "min", "loss_of_upright_posture"),
    CalibrationCheck("forward_lunge", "knee_tracking_ratio_min", "knee_tracking_ratio", "min", "front_knee_tracking_fault"),
    CalibrationCheck("forward_lunge", "front_foot_flatness_ratio_min", "front_foot_flatness_ratio", "min", "front_foot_not_flat"),
    CalibrationCheck("forward_lunge", "body_control_ratio_min", "body_control_ratio", "min", "loss_of_body_control"),
    CalibrationCheck("single_leg_dip", "balance_loss_ratio_max", "balance_loss_ratio", "max", "balance_loss"),
    CalibrationCheck("single_leg_dip", "body_rotation_ratio_max", "body_rotation_ratio", "max", "body_rotation"),
    CalibrationCheck("single_leg_dip", "foot_collapse_ratio_max", "foot_collapse_ratio", "max", "stance_foot_collapse"),
    CalibrationCheck("single_leg_dip", "knee_collapse_ratio_max", "knee_collapse_ratio", "max", "stance_knee_collapse"),
    CalibrationCheck("single_leg_dip", "hip_level_ratio_min", "hip_level_ratio", "min", "hips_not_level"),
    CalibrationCheck("shoulder_reach_behind_back", "hand_distance_ratio_max", "hand_distance_ratio", "max", "hands_too_far_apart"),
    CalibrationCheck("shoulder_reach_behind_back", "bottom_hand_reach_ratio_min", "bottom_hand_reach_ratio", "min", "bottom_hand_reach_limited"),
    CalibrationCheck("shoulder_reach_behind_back", "top_hand_midline_ratio_min", "top_hand_midline_ratio", "min", "top_hand_not_reaching_midline"),
    CalibrationCheck("shoulder_reach_behind_back", "lateral_flexion_ratio_max", "lateral_flexion_ratio", "max", "lateral_flexion_or_asymmetry"),
    CalibrationCheck("shoulder_reach_behind_back", "rounded_shoulder_ratio_max", "rounded_shoulder_ratio", "max", "rounded_shoulders"),
]


MIN_USABLE_EXAMPLES = 20
MIN_DISAGREEMENTS = 5
MAX_THRESHOLD_MOVE_RATIO = 0.10


def build_calibration_suggestions(
    entries: list[dict[str, Any]],
    thresholds: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for movement_key, movement_thresholds in thresholds.items():
        movement_entries = [
            entry for entry in entries
            if entry["movement_key"] == movement_key and _is_usable(entry)
        ]
        disagreement_count = sum(
            1 for entry in movement_entries
            if entry.get("app_score") is not None
            and entry["app_score"] != entry["provider_score"]
        )
        if len(movement_entries) < MIN_USABLE_EXAMPLES or disagreement_count < MIN_DISAGREEMENTS:
            continue

        for check in CALIBRATION_CHECKS:
            if check.movement_key != movement_key:
                continue
            current = movement_thresholds.get(check.threshold_key)
            if current is None:
                continue
            candidate = _build_check_suggestion(
                check,
                current=float(current),
                movement_entries=movement_entries,
                movement_disagreement_count=disagreement_count,
            )
            if candidate is not None:
                suggestions.append(candidate)
    return suggestions


def _is_usable(entry: dict[str, Any]) -> bool:
    if entry.get("app_source") == "fallback":
        return False
    quality = entry.get("app_quality") or {}
    if quality and quality.get("status") != "good":
        return False
    return entry.get("app_score") is not None and bool(entry.get("app_metrics"))


def _build_check_suggestion(
    check: CalibrationCheck,
    *,
    current: float,
    movement_entries: list[dict[str, Any]],
    movement_disagreement_count: int,
) -> dict[str, Any] | None:
    selected_fault_values = [
        float(entry["app_metrics"][check.metric_key])
        for entry in movement_entries
        if check.metric_key in entry["app_metrics"]
        and check.fault_key in entry["provider_faults"]
        and entry["app_score"] != entry["provider_score"]
    ]
    clear_fault_values = [
        float(entry["app_metrics"][check.metric_key])
        for entry in movement_entries
        if check.metric_key in entry["app_metrics"]
        and check.fault_key not in entry["provider_faults"]
        and entry["app_score"] < entry["provider_score"]
        and _violates_threshold(float(entry["app_metrics"][check.metric_key]), current, check.direction)
    ]

    selected_count = len(selected_fault_values)
    clear_count = len(clear_fault_values)
    if selected_count < MIN_DISAGREEMENTS and clear_count < MIN_DISAGREEMENTS:
        return None

    if selected_count >= clear_count:
        raw_target = float(median(selected_fault_values))
        suggested = _stricter_threshold(current, raw_target, check.direction)
        action = "stricter"
    else:
        raw_target = float(median(clear_fault_values))
        suggested = _looser_threshold(current, raw_target, check.direction)
        action = "looser"

    if suggested == current:
        return None

    return {
        "id": f"{check.movement_key}:{check.threshold_key}",
        "movement_key": check.movement_key,
        "threshold_key": check.threshold_key,
        "metric_key": check.metric_key,
        "direction": check.direction,
        "current_value": round(current, 6),
        "suggested_value": round(suggested, 6),
        "usable_examples": len(movement_entries),
        "disagreement_count": movement_disagreement_count,
        "selected_fault_count": selected_count,
        "rationale": (
            f"Provider corrections suggest a {action} threshold for {check.fault_key}."
        ),
    }


def _violates_threshold(value: float, threshold: float, direction: Direction) -> bool:
    return value > threshold if direction == "max" else value < threshold


def _stricter_threshold(current: float, target: float, direction: Direction) -> float:
    if direction == "max":
        if target >= current:
            return current
        return max(current * (1 - MAX_THRESHOLD_MOVE_RATIO), target)
    if target <= current:
        return current
    return min(current * (1 + MAX_THRESHOLD_MOVE_RATIO), target)


def _looser_threshold(current: float, target: float, direction: Direction) -> float:
    if direction == "max":
        if target <= current:
            return current
        return min(current * (1 + MAX_THRESHOLD_MOVE_RATIO), target)
    if target >= current:
        return current
    return max(current * (1 - MAX_THRESHOLD_MOVE_RATIO), target)
