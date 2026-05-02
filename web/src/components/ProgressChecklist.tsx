import type { MovementDefinition } from "../lib/types";

type ProgressChecklistProps = {
  movements: MovementDefinition[];
  completedKeys: Set<string>;
  selectedKey: string | null;
  onSelect: (movementKey: string) => void;
};

export function ProgressChecklist({
  movements,
  completedKeys,
  selectedKey,
  onSelect
}: ProgressChecklistProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/50">
            Movement checklist
          </p>
          <h2 className="mt-1 text-lg font-semibold">Five-movement flow</h2>
        </div>
        <div className="rounded-full bg-mist px-3 py-1 text-sm font-semibold text-accent">
          {completedKeys.size}/{movements.length}
        </div>
      </div>
      <div className="mt-4 grid gap-2">
        {movements.map((movement, index) => {
          const isCompleted = completedKeys.has(movement.key);
          const isSelected = selectedKey === movement.key;
          return (
            <button
              key={movement.key}
              className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                isSelected
                  ? "border-accent bg-mist"
                  : "border-rim bg-panel hover:border-accent/50"
              }`}
              onClick={() => onSelect(movement.key)}
              type="button"
            >
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-ink/40">
                  Movement {index + 1}
                </p>
                <p className="font-semibold">{movement.label}</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  isCompleted
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-panel-mid text-ink/50"
                }`}
              >
                {isCompleted ? "Saved" : "Pending"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

