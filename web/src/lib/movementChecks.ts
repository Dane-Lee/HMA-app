export type CheckDefinition = {
  label: string;
  metricKey: string;
  thresholdKey: string;
  direction: "min" | "max";
  unit?: string;
};

export const MOVEMENT_CHECKS: Record<string, CheckDefinition[]> = {
  cervical_rotation: [
    {
      label: "Chin midline clearance",
      metricKey: "chin_midline_clearance_ratio",
      thresholdKey: "chin_midline_clearance_ratio_min",
      direction: "min",
    },
    {
      label: "Shoulder drift",
      metricKey: "shoulder_drift_ratio",
      thresholdKey: "shoulder_drift_ratio_max",
      direction: "max",
    },
    {
      label: "Forward head",
      metricKey: "forward_head_ratio",
      thresholdKey: "forward_head_ratio_max",
      direction: "max",
    },
    {
      label: "Neck path deviation",
      metricKey: "neck_path_deviation_ratio",
      thresholdKey: "neck_path_deviation_ratio_max",
      direction: "max",
    },
    {
      label: "Excessive effort",
      metricKey: "excessive_effort_ratio",
      thresholdKey: "excessive_effort_ratio_max",
      direction: "max",
    },
  ],
  trunk_rotation: [
    {
      label: "Rotation angle",
      metricKey: "trunk_rotation_angle_degrees",
      thresholdKey: "rotation_angle_min_degrees",
      direction: "min",
      unit: "°",
    },
    {
      label: "Lower extremity movement",
      metricKey: "lower_extremity_movement_ratio",
      thresholdKey: "lower_extremity_movement_ratio_max",
      direction: "max",
    },
    {
      label: "Spine-pelvis deviation",
      metricKey: "spine_pelvis_deviation_ratio",
      thresholdKey: "spine_pelvis_deviation_ratio_max",
      direction: "max",
    },
    {
      label: "Cervical motion",
      metricKey: "cervical_motion_ratio",
      thresholdKey: "cervical_motion_ratio_max",
      direction: "max",
    },
    {
      label: "Excessive effort",
      metricKey: "excessive_effort_ratio",
      thresholdKey: "excessive_effort_ratio_max",
      direction: "max",
    },
  ],
  forward_lunge: [
    {
      label: "Back knee depth",
      metricKey: "back_knee_depth_ratio",
      thresholdKey: "back_knee_depth_ratio_min",
      direction: "min",
    },
    {
      label: "Upright posture",
      metricKey: "upright_posture_ratio",
      thresholdKey: "upright_posture_ratio_min",
      direction: "min",
    },
    {
      label: "Knee tracking",
      metricKey: "knee_tracking_ratio",
      thresholdKey: "knee_tracking_ratio_min",
      direction: "min",
    },
    {
      label: "Front foot flatness",
      metricKey: "front_foot_flatness_ratio",
      thresholdKey: "front_foot_flatness_ratio_min",
      direction: "min",
    },
    {
      label: "Body control",
      metricKey: "body_control_ratio",
      thresholdKey: "body_control_ratio_min",
      direction: "min",
    },
  ],
  single_leg_dip: [
    {
      label: "Balance loss",
      metricKey: "balance_loss_ratio",
      thresholdKey: "balance_loss_ratio_max",
      direction: "max",
    },
    {
      label: "Body rotation",
      metricKey: "body_rotation_ratio",
      thresholdKey: "body_rotation_ratio_max",
      direction: "max",
    },
    {
      label: "Foot collapse",
      metricKey: "foot_collapse_ratio",
      thresholdKey: "foot_collapse_ratio_max",
      direction: "max",
    },
    {
      label: "Knee collapse",
      metricKey: "knee_collapse_ratio",
      thresholdKey: "knee_collapse_ratio_max",
      direction: "max",
    },
    {
      label: "Hip level",
      metricKey: "hip_level_ratio",
      thresholdKey: "hip_level_ratio_min",
      direction: "min",
    },
  ],
  shoulder_reach_behind_back: [
    {
      label: "Hand gap",
      metricKey: "hand_distance_ratio",
      thresholdKey: "hand_distance_ratio_max",
      direction: "max",
    },
    {
      label: "Bottom hand reach",
      metricKey: "bottom_hand_reach_ratio",
      thresholdKey: "bottom_hand_reach_ratio_min",
      direction: "min",
    },
    {
      label: "Top hand midline",
      metricKey: "top_hand_midline_ratio",
      thresholdKey: "top_hand_midline_ratio_min",
      direction: "min",
    },
    {
      label: "Lateral flexion",
      metricKey: "lateral_flexion_ratio",
      thresholdKey: "lateral_flexion_ratio_max",
      direction: "max",
    },
    {
      label: "Rounded shoulders",
      metricKey: "rounded_shoulder_ratio",
      thresholdKey: "rounded_shoulder_ratio_max",
      direction: "max",
    },
  ],
};
