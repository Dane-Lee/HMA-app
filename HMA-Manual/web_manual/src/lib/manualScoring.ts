export type ManualFaultPrompt = {
  key: string;
  label: string;
};

export const MANUAL_FAULT_PROMPTS: Record<string, ManualFaultPrompt[]> = {
  cervical_rotation: [
    { key: "chin_does_not_clear_clavicle_midline", label: "Chin does not clear clavicle midline" },
    { key: "shoulder_drift", label: "Shoulder drift" },
    { key: "forward_head_or_rounded_shoulder_setup", label: "Forward head or rounded shoulder setup" },
    { key: "neck_deviation_from_midline", label: "Neck deviation from midline" },
    { key: "excessive_effort_placeholder", label: "Excessive effort" },
  ],
  trunk_rotation: [
    { key: "rotation_below_45_degrees", label: "Rotation below expected range" },
    { key: "excessive_lower_extremity_movement", label: "Lower body movement" },
    { key: "spine_or_pelvis_deviation", label: "Spine or pelvis deviation" },
    { key: "excessive_cervical_motion", label: "Excessive neck motion" },
    { key: "excessive_effort_placeholder", label: "Excessive effort" },
  ],
  forward_lunge: [
    { key: "back_knee_depth_insufficient", label: "Back knee depth insufficient" },
    { key: "loss_of_upright_posture", label: "Loss of upright posture" },
    { key: "front_knee_tracking_fault", label: "Front knee tracking fault" },
    { key: "front_foot_not_flat", label: "Front foot not flat" },
    { key: "loss_of_body_control", label: "Loss of body control" },
    { key: "excessive_effort_placeholder", label: "Excessive effort" },
  ],
  single_leg_dip: [
    { key: "balance_loss", label: "Balance loss" },
    { key: "body_rotation", label: "Body rotation" },
    { key: "stance_foot_collapse", label: "Stance foot collapse" },
    { key: "stance_knee_collapse", label: "Stance knee collapse" },
    { key: "hips_not_level", label: "Hips not level" },
    { key: "excessive_effort_placeholder", label: "Excessive effort" },
  ],
  shoulder_reach_behind_back: [
    { key: "hands_too_far_apart", label: "Hands too far apart" },
    { key: "bottom_hand_reach_limited", label: "Bottom hand reach limited" },
    { key: "top_hand_not_reaching_midline", label: "Top hand not reaching midline" },
    { key: "lateral_flexion_or_asymmetry", label: "Lateral flexion or asymmetry" },
    { key: "rounded_shoulders", label: "Rounded shoulders" },
    { key: "finger_walking_placeholder", label: "Finger walking" },
  ],
};
