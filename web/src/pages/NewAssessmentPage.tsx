import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createAssessment } from "../lib/api";
import { buildConsentPayload, PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type { ScoringMode } from "../lib/types";

export function NewAssessmentPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [scoringMode, setScoringMode] = useState<ScoringMode>("ai_assisted");
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSaving(true);
    try {
      const assessment = await createAssessment(name.trim(), buildConsentPayload(), scoringMode);
      navigate(`/assessments/${assessment.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create assessment.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Assessment setup</p>
        <h2 className="mt-2 text-2xl font-semibold">Start a new HMA assessment</h2>
        <p className="mt-3 text-sm text-ink/70">
          This workflow stores only structured scoring results. Raw video is
          processed for scoring and deleted immediately after analysis.
        </p>
        <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
          {PRIVACY_POSTURE_STATEMENT}
        </p>
      </section>

      <form className="card grid gap-4" onSubmit={handleSubmit}>
        <label className="grid gap-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold">Participant name or ID</span>
            {name.length > 80 ? (
              <span className={`text-xs tabular-nums ${name.length >= 120 ? "text-rose-600" : "text-ink/45"}`}>
                {name.length}/120
              </span>
            ) : null}
          </div>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none transition focus:border-accent"
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            placeholder="Enter participant name or ID"
            required
            value={name}
          />
        </label>

        <fieldset className="grid gap-2">
          <legend className="text-sm font-semibold">Scoring mode</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {([
              ["ai_assisted", "AI assisted", "Analyze captures and allow manual correction."],
              ["manual", "Manual", "Enter provider scores for every movement."]
            ] as const).map(([value, label, description]) => (
              <label
                className={`rounded-2xl border px-4 py-3 text-sm transition ${
                  scoringMode === value
                    ? "border-accent bg-mist text-ink"
                    : "border-rim bg-panel text-ink/75"
                }`}
                key={value}
              >
                <input
                  checked={scoringMode === value}
                  className="sr-only"
                  onChange={() => setScoringMode(value)}
                  type="radio"
                />
                <span className="block font-semibold">{label}</span>
                <span className="mt-1 block text-xs text-ink/55">{description}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <label className="flex items-start gap-3 rounded-2xl bg-panel px-4 py-4 text-sm text-ink/75">
          <input
            checked={accepted}
            className="mt-1 h-4 w-4 rounded border-slate-300 text-accent"
            onChange={(event) => setAccepted(event.target.checked)}
            type="checkbox"
          />
          <span>
            I confirm participation is voluntary, the assessment is limited to
            ergonomic/wellness screening and provider support, structured results
            will be retained under the configured retention policy, raw live
            capture video is deleted immediately after analysis, and results are
            not used as a stand-alone basis for employment decisions.
          </span>
        </label>

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        <button className="button-primary" disabled={!accepted || !name.trim() || isSaving} type="submit">
          {isSaving ? "Creating..." : "Create assessment"}
        </button>
      </form>
    </div>
  );
}
