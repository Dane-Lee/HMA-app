import type { MovementDefinition } from "../lib/types";

type ProgressChecklistProps = {
  movements: MovementDefinition[];
  completedKeys: Set<string>;
  selectedKey: string;
  onSelect: (movementKey: string) => void;
};

export function ProgressChecklist({ movements, completedKeys, selectedKey, onSelect }: ProgressChecklistProps) {
  return (
    <section className="grid gap-2 sm:grid-cols-5">
      {movements.map((movement, index) => {
        const completed = completedKeys.has(movement.key);
        const selected = selectedKey === movement.key;
        return (
          <button
            className={`rounded-2xl border px-3 py-3 text-left transition ${
              selected ? "border-accent bg-mist" : "border-rim bg-panel"
            }`}
            key={movement.key}
            onClick={() => onSelect(movement.key)}
            type="button"
          >
            <p className="text-xs uppercase tracking-[0.2em] text-ink/40">Move {index + 1}</p>
            <p className="mt-1 text-sm font-semibold">{movement.label}</p>
            <p className={`mt-2 text-xs ${completed ? "text-emerald-300" : "text-ink/45"}`}>
              {completed ? "Scored" : "Pending"}
            </p>
          </button>
        );
      })}
    </section>
  );
}
