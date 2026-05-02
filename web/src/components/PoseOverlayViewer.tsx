import { useEffect, useMemo, useRef, useState } from "react";

import { prettyFault } from "../lib/formatters";
import { MOVEMENT_CHECKS } from "../lib/movementChecks";
import type {
  MovementThresholds,
  OverlayAnnotation,
  PoseFrame,
  PoseLandmark,
  PoseTrace
} from "../lib/types";

type PoseOverlayViewerProps = {
  poseTrace?: PoseTrace | null;
  videoUrl?: string | null;
  movementKey: string;
  metrics?: Record<string, number> | null;
  thresholds?: MovementThresholds;
  detectedFaults?: string[];
  title?: string;
};

type SkeletonSegment = {
  from: string;
  to: string;
  group: string;
};

const SKELETON_SEGMENTS: SkeletonSegment[] = [
  { from: "left_shoulder", to: "right_shoulder", group: "shoulders" },
  { from: "left_hip", to: "right_hip", group: "hips" },
  { from: "left_shoulder", to: "left_hip", group: "trunk" },
  { from: "right_shoulder", to: "right_hip", group: "trunk" },
  { from: "nose", to: "left_shoulder", group: "head_neck" },
  { from: "nose", to: "right_shoulder", group: "head_neck" },
  { from: "left_shoulder", to: "left_elbow", group: "left_arm" },
  { from: "left_elbow", to: "left_wrist", group: "left_arm" },
  { from: "right_shoulder", to: "right_elbow", group: "right_arm" },
  { from: "right_elbow", to: "right_wrist", group: "right_arm" },
  { from: "left_hip", to: "left_knee", group: "left_leg" },
  { from: "left_knee", to: "left_ankle", group: "left_leg" },
  { from: "right_hip", to: "right_knee", group: "right_leg" },
  { from: "right_knee", to: "right_ankle", group: "right_leg" },
  { from: "left_ankle", to: "left_heel", group: "left_foot" },
  { from: "left_heel", to: "left_foot_index", group: "left_foot" },
  { from: "right_ankle", to: "right_heel", group: "right_foot" },
  { from: "right_heel", to: "right_foot_index", group: "right_foot" }
];

const FAULT_GROUPS: Record<string, string[]> = {
  back_knee_depth: ["left_leg", "right_leg"],
  balance_loss: ["hips", "trunk"],
  body_control: ["hips", "trunk"],
  body_rotation: ["shoulders", "hips", "trunk"],
  bottom_hand_reach: ["left_arm", "right_arm"],
  cervical_motion: ["head_neck"],
  chin_midline_clearance: ["head_neck"],
  excessive_effort: ["head_neck", "shoulders", "trunk"],
  finger_walk: ["left_arm", "right_arm"],
  foot_collapse: ["left_foot", "right_foot"],
  forward_head: ["head_neck"],
  front_foot_flatness: ["left_foot", "right_foot"],
  hand_distance: ["left_arm", "right_arm"],
  hip_level: ["hips"],
  knee_collapse: ["left_leg", "right_leg"],
  knee_tracking: ["left_leg", "right_leg"],
  lateral_flexion: ["trunk"],
  lower_extremity_movement: ["left_leg", "right_leg", "hips"],
  neck_path_deviation: ["head_neck"],
  rounded_shoulder: ["shoulders", "head_neck"],
  shoulder_drift: ["shoulders"],
  spine_pelvis_deviation: ["shoulders", "hips", "trunk"],
  top_hand_midline: ["left_arm", "right_arm"],
  trunk_rotation_angle: ["shoulders", "hips", "trunk"],
  upright_posture: ["trunk"]
};

function toLandmarkMap(frame: PoseFrame) {
  return new Map(frame.landmarks.map((landmark) => [landmark.name, landmark]));
}

function clampUnit(value: number) {
  return Math.max(0, Math.min(1, value));
}

function segmentPoint(landmark: PoseLandmark, width: number, height: number) {
  return {
    x: clampUnit(landmark.x) * width,
    y: clampUnit(landmark.y) * height
  };
}

function pickFrame(frames: PoseFrame[], timeSeconds: number, fallbackIndex: number) {
  if (frames.length === 0) {
    return undefined;
  }
  if (timeSeconds <= 0) {
    return frames[Math.min(fallbackIndex, frames.length - 1)];
  }
  return frames.reduce((closest, frame) => (
    Math.abs(frame.time_seconds - timeSeconds) < Math.abs(closest.time_seconds - timeSeconds)
      ? frame
      : closest
  ), frames[0]);
}

function faultGroups(faults: string[] = []) {
  const groups = new Set<string>();
  faults.forEach((fault) => {
    const normalized = fault.replace(/_placeholder$/, "");
    Object.entries(FAULT_GROUPS).forEach(([key, nextGroups]) => {
      if (normalized.includes(key)) {
        nextGroups.forEach((group) => groups.add(group));
      }
    });
  });
  return groups;
}

function buildAnnotations(
  movementKey: string,
  metrics: Record<string, number> | null | undefined,
  thresholds: MovementThresholds | undefined,
  detectedFaults: string[] = []
): OverlayAnnotation[] {
  const checks = MOVEMENT_CHECKS[movementKey] ?? [];
  const annotations = checks.flatMap<OverlayAnnotation>((check) => {
    const value = metrics?.[check.metricKey];
    const threshold = thresholds?.[check.thresholdKey];
    if (value === undefined || threshold === undefined) {
      return [];
    }
    const isFault = check.direction === "max" ? value > threshold : value < threshold;
    const isNear = check.direction === "max" ? value > threshold * 0.8 : value < threshold * 1.2;
    return [{
      label: check.label,
      detail: `App detected ${value.toFixed(check.unit ? 0 : 2)}${check.unit ?? ""} ${
        check.direction === "max" ? "against max" : "against min"
      } ${threshold}${check.unit ?? ""}.`,
      tone: isFault ? "fault" : isNear ? "warning" : "good"
    }];
  });

  detectedFaults.forEach((fault) => {
    if (!annotations.some((annotation) => fault.includes(annotation.label.toLowerCase().replaceAll(" ", "_")))) {
      annotations.push({
        label: prettyFault(fault),
        detail: "App detected this scoring item; provider review recommended.",
        tone: fault.endsWith("_placeholder") ? "warning" : "fault"
      });
    }
  });

  return annotations.slice(0, 5);
}

export function PoseOverlayViewer({
  poseTrace,
  videoUrl,
  movementKey,
  metrics,
  thresholds,
  detectedFaults = [],
  title = "Pose overlay"
}: PoseOverlayViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [showConfidence, setShowConfidence] = useState(false);
  const [showExplanation, setShowExplanation] = useState(true);
  const [frameIndex, setFrameIndex] = useState(0);
  const [, setTick] = useState(0);
  const frames = poseTrace?.frames ?? [];
  const annotations = useMemo(
    () => buildAnnotations(movementKey, metrics, thresholds, detectedFaults),
    [detectedFaults, metrics, movementKey, thresholds]
  );
  const highlightedGroups = useMemo(() => faultGroups(detectedFaults), [detectedFaults]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !poseTrace || frames.length === 0) {
      return;
    }
    const parent = canvas.parentElement;
    const rect = parent?.getBoundingClientRect();
    const width = Math.max(320, Math.round(rect?.width ?? 640));
    const height = Math.max(180, Math.round(rect?.height ?? 360));
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const currentTime = videoRef.current?.currentTime ?? 0;
    const frame = pickFrame(frames, currentTime, frameIndex);
    if (!frame) {
      return;
    }
    const landmarks = toLandmarkMap(frame);
    context.clearRect(0, 0, width, height);
    if (!videoUrl) {
      context.fillStyle = "#0f172a";
      context.fillRect(0, 0, width, height);
    }

    if (showSkeleton) {
      SKELETON_SEGMENTS.forEach((segment) => {
        const start = landmarks.get(segment.from);
        const end = landmarks.get(segment.to);
        if (!start || !end || start.visibility < 0.2 || end.visibility < 0.2) {
          return;
        }
        const startPoint = segmentPoint(start, width, height);
        const endPoint = segmentPoint(end, width, height);
        const isHighlighted = showExplanation && highlightedGroups.has(segment.group);
        context.strokeStyle = isHighlighted ? "#ef4444" : "#38bdf8";
        context.lineWidth = isHighlighted ? 4 : 3;
        context.globalAlpha = Math.min(1, Math.max(0.35, (start.visibility + end.visibility) / 2));
        context.beginPath();
        context.moveTo(startPoint.x, startPoint.y);
        context.lineTo(endPoint.x, endPoint.y);
        context.stroke();
      });

      frame.landmarks.forEach((landmark) => {
        if (landmark.visibility < 0.2) {
          return;
        }
        const point = segmentPoint(landmark, width, height);
        context.globalAlpha = showConfidence ? Math.max(0.2, landmark.visibility) : 0.9;
        context.fillStyle = landmark.visibility >= 0.5 ? "#f8fafc" : "#f59e0b";
        context.beginPath();
        context.arc(point.x, point.y, showConfidence ? 4 : 3, 0, Math.PI * 2);
        context.fill();
      });
      context.globalAlpha = 1;
    }
  }, [
    frameIndex,
    frames,
    highlightedGroups,
    poseTrace,
    showConfidence,
    showExplanation,
    showSkeleton,
    videoUrl
  ]);

  if (!poseTrace || frames.length === 0) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-rim bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Provider overlay</p>
          <h4 className="font-semibold">{title}</h4>
        </div>
        <p className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
          {poseTrace.frames.length}/{poseTrace.sampled_frames} frames
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className={`rounded-full px-3 py-2 text-xs font-semibold ${showSkeleton ? "bg-accent text-white" : "bg-panel-mid text-ink/70"}`}
          onClick={() => setShowSkeleton((value) => !value)}
          type="button"
        >
          Skeleton
        </button>
        <button
          className={`rounded-full px-3 py-2 text-xs font-semibold ${showConfidence ? "bg-accent text-white" : "bg-panel-mid text-ink/70"}`}
          onClick={() => setShowConfidence((value) => !value)}
          type="button"
        >
          Confidence
        </button>
        <button
          className={`rounded-full px-3 py-2 text-xs font-semibold ${showExplanation ? "bg-accent text-white" : "bg-panel-mid text-ink/70"}`}
          onClick={() => setShowExplanation((value) => !value)}
          type="button"
        >
          HMA explanation
        </button>
      </div>

      <div className="relative mt-3 aspect-video overflow-hidden rounded-2xl bg-slate-950">
        {videoUrl ? (
          <video
            className="absolute inset-0 h-full w-full object-cover"
            controls
            onLoadedMetadata={() => setTick((value) => value + 1)}
            onTimeUpdate={() => setTick((value) => value + 1)}
            playsInline
            ref={videoRef}
            src={videoUrl}
          />
        ) : null}
        <canvas className="absolute inset-0 h-full w-full" ref={canvasRef} />
      </div>

      {!videoUrl ? (
        <label className="mt-3 grid gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">
          Skeleton frame
          <input
            max={Math.max(frames.length - 1, 0)}
            min={0}
            onChange={(event) => setFrameIndex(Number(event.target.value))}
            type="range"
            value={frameIndex}
          />
        </label>
      ) : null}

      {showExplanation && annotations.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {annotations.map((annotation) => (
            <div
              className={`rounded-xl px-3 py-2 text-sm ${
                annotation.tone === "fault"
                  ? "bg-rose-500/15 text-rose-200"
                  : annotation.tone === "warning"
                    ? "bg-amber-500/15 text-amber-100"
                    : annotation.tone === "good"
                      ? "bg-emerald-500/15 text-emerald-200"
                      : "bg-panel-mid text-ink/70"
              }`}
              key={`${annotation.label}-${annotation.detail}`}
            >
              <p className="font-semibold capitalize">{annotation.label}</p>
              <p className="mt-1 opacity-80">{annotation.detail}</p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
