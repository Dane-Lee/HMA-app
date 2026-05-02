import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PoseOverlayViewer } from "./PoseOverlayViewer";
import type { PoseTrace } from "../lib/types";

const trace: PoseTrace = {
  schema_version: 1,
  source: "mediapipe",
  movement_key: "trunk_rotation",
  side: "right",
  width: 640,
  height: 360,
  fps: 30,
  duration_seconds: 2,
  sampled_frames: 1,
  frames: [
    {
      time_seconds: 0,
      landmarks: [
        { name: "nose", x: 0.5, y: 0.15, z: 0, visibility: 0.9 },
        { name: "left_shoulder", x: 0.4, y: 0.3, z: 0, visibility: 0.9 },
        { name: "right_shoulder", x: 0.6, y: 0.3, z: 0, visibility: 0.9 },
        { name: "left_hip", x: 0.44, y: 0.6, z: 0, visibility: 0.9 },
        { name: "right_hip", x: 0.56, y: 0.6, z: 0, visibility: 0.9 },
      ],
    },
  ],
};

describe("PoseOverlayViewer", () => {
  it("renders provider overlay controls and HMA explanation labels", () => {
    render(
      <PoseOverlayViewer
        detectedFaults={["lower_extremity_movement"]}
        metrics={{ trunk_rotation_angle_degrees: 42 }}
        movementKey="trunk_rotation"
        poseTrace={trace}
        thresholds={{ rotation_angle_min_degrees: 45 }}
      />
    );

    expect(screen.getByRole("button", { name: /skeleton/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /hma explanation/i })).toBeInTheDocument();
    expect(screen.getByText(/rotation angle/i)).toBeInTheDocument();
    expect(screen.getAllByText(/app detected/i).length).toBeGreaterThan(0);
  });
});
