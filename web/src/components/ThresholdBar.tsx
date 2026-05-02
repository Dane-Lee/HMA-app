type ThresholdBarProps = {
  label: string;
  value: number;
  threshold: number;
  direction: "min" | "max";
  unit?: string;
};

export function ThresholdBar({ label, value, threshold, direction, unit = "" }: ThresholdBarProps) {
  const isFault = direction === "max" ? value >= threshold : value <= threshold;
  const isWarning =
    !isFault &&
    (direction === "max" ? value >= threshold * 0.8 : value <= threshold * 1.2);

  // Bar scale: 0 → threshold*2. Threshold marker sits at exactly 50%.
  const fillPct = Math.min(100, Math.max(0, (value / (threshold * 2)) * 100));

  const barColor = isFault ? "bg-rose-500" : isWarning ? "bg-amber-400" : "bg-emerald-500";
  const textColor = isFault ? "text-rose-400" : isWarning ? "text-amber-300" : "text-emerald-400";

  const fmt = (v: number) =>
    unit === "°" ? `${Math.round(v)}` : v < 1 ? v.toFixed(3) : v.toFixed(1);

  return (
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="text-ink/70">{label}</span>
        <span className={`font-semibold tabular-nums ${textColor}`}>
          {fmt(value)}{unit}
          <span className="font-normal text-ink/40 ml-1">
            / {direction === "max" ? "≤" : "≥"} {fmt(threshold)}{unit}
          </span>
        </span>
      </div>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-panel-mid">
        <div
          className={`absolute left-0 top-0 h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${fillPct}%` }}
        />
        <div
          className="absolute top-0 h-full w-0.5 bg-ink/30"
          style={{ left: "50%" }}
        />
      </div>
    </div>
  );
}
