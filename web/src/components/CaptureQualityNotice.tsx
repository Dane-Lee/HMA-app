import type { CaptureQuality } from "../lib/types";

type CaptureQualityNoticeProps = {
  quality?: CaptureQuality | null;
};

const WARNING_COPY: Record<string, string> = {
  legacy_capture_no_pose_quality: "This older capture does not include pose quality data.",
  limited_pose_samples: "Only a small number of pose samples were available.",
  low_pose_detection_rate: "Pose detection was inconsistent across the clip.",
  low_required_landmark_visibility: "One or more key joints were hard to see.",
  missing_video_dimensions: "Video dimensions were unavailable.",
  pose_overlay_unavailable_for_fallback_scoring: "Pose overlay is unavailable for fallback scoring.",
  pose_overlays_disabled: "Pose overlays are disabled for this environment."
};

export function CaptureQualityNotice({ quality }: CaptureQualityNoticeProps) {
  if (!quality) {
    return null;
  }

  const isGood = quality.status === "good";
  const statusLabel = isGood
    ? "Pose quality good"
    : quality.overlay_available
      ? "Pose quality warning"
      : "Pose overlay unavailable";
  const toneClass = isGood
    ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-200"
    : quality.overlay_available
      ? "border-amber-500/30 bg-amber-500/15 text-amber-100"
      : "border-rim bg-panel text-ink/70";

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm ${toneClass}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">{statusLabel}</p>
        <p className="text-xs uppercase tracking-[0.2em] opacity-70">
          {quality.source} | {Math.round(quality.detection_rate * 100)}%
        </p>
      </div>
      {quality.warnings.length > 0 ? (
        <ul className="mt-2 grid gap-1">
          {quality.warnings.map((warning) => (
            <li key={warning}>{WARNING_COPY[warning] ?? warning.replaceAll("_", " ")}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 opacity-80">
          App-detected pose data is available for provider review.
        </p>
      )}
    </div>
  );
}
